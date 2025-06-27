# ============================================
# IMPORTS PRINCIPAIS
# ============================================
from fastapi import FastAPI, Form, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# Imports para TTS
from transformers import VitsModel, AutoTokenizer
from accelerate import Accelerator
from scipy.io.wavfile import write
from pydub import AudioSegment

# Imports padrão Python
import torch
import numpy as np
import os
import uuid
import logging
import time
from datetime import datetime

# Importar sistema de autenticação
from .auth import (
    get_current_active_user,
    get_admin_user, 
    get_rate_limited_user,
    create_access_token,
    revoke_token,
    AuthenticationError,
    PermissionError,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from .database import db_manager

# Importar o router de monitoring
try:
    from .monitoring import router as monitoring_router
except ImportError:
    monitoring_router = None

# ============================================
# CONFIGURAÇÃO DA APLICAÇÃO
# ============================================
app = FastAPI(
    title="Hebrew & Greek TTS API (Authenticated)", 
    description="API especializada em TTS para Hebraico e Grego usando MMS-TTS com autenticação",
    version="2.1.0"
)

# ============================================
# MIDDLEWARES (ORDEM IMPORTANTE!)
# ============================================

# 1. GZip Middleware (deve ser adicionado PRIMEIRO)
app.add_middleware(
    GZipMiddleware, 
    minimum_size=1000,  # Compactar apenas responses > 1KB
    compresslevel=6     # Nível de compressão (1-9, 6 é bom equilíbrio)
)

# 2. CORS Middleware (depois do GZip)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure adequadamente em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas de monitoring (apenas para admins)
if monitoring_router:
    app.include_router(
        monitoring_router, 
        prefix="/monitoring", 
        tags=["monitoring"],
        dependencies=[Depends(get_admin_user)]  # Apenas admins
    )

# ============================================
# CONFIGURAÇÃO DE LOGGING
# ============================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Verificar se GPU está disponível
has_cuda = torch.cuda.is_available()
logger.info(f"CUDA available: {has_cuda}")

# Inicializar Accelerator com configuração correta para CPU/GPU
if has_cuda:
    # Configuração para GPU (com FP16)
    accelerator = Accelerator(
        mixed_precision="fp16",
        device_placement=True
    )
    torch_dtype = torch.float16
else:
    # Configuração para CPU (sem FP16 - usar FP32)
    accelerator = Accelerator(
        mixed_precision="no",  # Desabilitar mixed precision na CPU
        cpu=True,
        device_placement=True
    )
    torch_dtype = torch.float32

device = accelerator.device
logger.info(f"Using device: {device} with accelerate")
logger.info(f"Mixed precision: {accelerator.mixed_precision}")
logger.info(f"Torch dtype: {torch_dtype}")

# Modelos carregados dinamicamente
models = {}
tokenizers = {}

# Configuração dos modelos disponíveis
MODEL_CONFIG = {
    "hebrew": {
        "name": "MMS-TTS Hebrew",
        "model_id": "facebook/mms-tts-heb",
        "type": "mms",
        "supported_languages": {"heb": "Hebrew"}
    },
    "greek": {
        "name": "MMS-TTS Greek", 
        "model_id": "facebook/mms-tts-ell",
        "type": "mms",
        "supported_languages": {"ell": "Greek"}
    },
    "portuguese": {
        "name": "MMS-TTS Portuguese",
        "model_id": "facebook/mms-tts-por",
        "type": "mms",
        "supported_languages": {"por": "Portuguese"}
    },
}

# Presets de voz (simplificados para MMS-TTS)
VOICE_PRESETS = {
    "natural": {
        "description": "Voz natural balanceada",
        "length_scale": 1.0
    },
    "expressive": {
        "description": "Voz ligeiramente mais lenta (mais expressiva)",
        "length_scale": 0.9
    },
    "robotic": {
        "description": "Voz natural (limitações do modelo)",
        "length_scale": 1.0
    },
    "slow": {
        "description": "Fala lenta para aprendizado",
        "length_scale": 1.5
    },
    "fast": {
        "description": "Fala rápida",
        "length_scale": 0.7
    }
}

def load_model(model_key: str):
    """Carrega modelo dinamicamente com accelerate (compatível CPU/GPU)"""
    if model_key in models:
        return models[model_key], tokenizers[model_key]
    
    config = MODEL_CONFIG[model_key]
    logger.info(f"Loading model with accelerate: {config['name']} (dtype: {torch_dtype})")
    
    # Carregar modelo com dtype correto para CPU/GPU
    model = VitsModel.from_pretrained(
        config["model_id"],
        torch_dtype=torch_dtype,
        device_map="auto" if has_cuda else None
    )
    
    tokenizer = AutoTokenizer.from_pretrained(config["model_id"])
    
    # Preparar modelo com accelerator
    model = accelerator.prepare(model)
    
    models[model_key] = model
    tokenizers[model_key] = tokenizer
    
    logger.info(f"Model {config['name']} loaded successfully with accelerate")
    return model, tokenizer

def get_model_for_language(lang: str):
    """Determina qual modelo usar para um idioma específico"""
    for model_key, config in MODEL_CONFIG.items():
        if lang in config["supported_languages"]:
            return model_key, config
    return None, None

# Função para inicialização automática na primeira execução
def initialize_app():
    """Inicializa aplicação na primeira execução"""
    # Verificar se deve inicializar dados padrão automaticamente
    auto_init = os.getenv("AUTO_INIT_DEFAULT_DATA", "false").lower() == "true"
    
    if auto_init:
        logger.info("Auto-initializing default data...")
        try:
            result = db_manager.initialize_default_data()
            if result:
                logger.info("Default data initialized successfully")
                # Log das credenciais criadas (apenas no desenvolvimento)
                if os.getenv("ENVIRONMENT", "production") == "development":
                    if "admin_user" in result and "credentials" in result["admin_user"]:
                        logger.info(f"Admin credentials: {result['admin_user']['credentials']}")
                    if "demo_user" in result and "credentials" in result["demo_user"]:
                        logger.info(f"Demo credentials: {result['demo_user']['credentials']}")
            else:
                logger.info("Default data already exists or initialization skipped")
        except Exception as e:
            logger.error(f"Error during auto-initialization: {e}")

# Chamar inicialização na startup
initialize_app()

# ============================================
# ROTAS DE AUTENTICAÇÃO
# ============================================

@app.post("/auth/login")
def login(
    request: Request,
    username: str = Form(...), 
    password: str = Form(...)
):
    """Login com usuário/senha (retorna JWT)"""
    ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    
    user_data = db_manager.authenticate_user(username, password, ip_address)
    if not user_data:
        raise AuthenticationError("Invalid username or password")
    
    token, jti = create_access_token({
        "sub": user_data["username"],
        "user_id": user_data["id"],
        "permissions": user_data["permissions"],
        "is_admin": user_data["is_admin"],
        "rate_limit": user_data["rate_limit"]
    })
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user_data["id"],
            "username": user_data["username"],
            "email": user_data["email"],
            "permissions": user_data["permissions"],
            "is_admin": user_data["is_admin"],
            "rate_limit": user_data["rate_limit"]
        }
    }

@app.post("/auth/logout")
def logout(current_user: dict = Depends(get_current_active_user)):
    """Logout (revoga token JWT)"""
    if current_user["type"] == "jwt" and "jti" in current_user:
        revoke_token(current_user["jti"])
        return {"message": "Successfully logged out"}
    
    return {"message": "No active session to logout"}

@app.get("/auth/me")
def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """Informações do usuário atual"""
    stats = {}
    if current_user["type"] == "jwt" and "user_id" in current_user:
        stats = db_manager.get_user_stats(current_user["user_id"])
    
    return {
        "user": current_user,
        "authenticated": True,
        "stats": stats
    }

# ============================================
# ROTAS PROTEGIDAS
# ============================================

@app.get("/")
def root():
    """Endpoint público - informações básicas"""
    return {
        "message": "Hebrew & Greek TTS API (Authenticated)",
        "version": "2.1.0",
        "authentication": {
            "required": True,
            "methods": ["JWT Bearer Token", "API Key"],
            "endpoints": {
                "login": "/auth/login",
                "profile": "/auth/me"
            }
        },
        "models": list(MODEL_CONFIG.keys()),
        "supported_languages": ["heb (Hebrew)", "ell (Greek)", "por (Portuguese)"],
        "public_endpoints": ["/", "/docs", "/auth/login"],
        "protected_endpoints": ["/speak", "/models", "/languages", "/health"]
    }

@app.post("/speak")
def speak(
    text: str = Form(...), 
    lang: str = Form(...), 
    model: str = Form(default="auto"),
    preset: str = Form(default=None),
    speed: float = Form(default=None, ge=0.1, le=3.0),
    current_user: dict = Depends(get_rate_limited_user)  # Autenticação + Rate Limit
):
    """
    Gera áudio com autenticação e rate limiting
    """
    try:
        logger.info(f"TTS request from user: {current_user.get('name', 'Unknown')} - Text: '{text[:50]}...'")
        
        # Determinar configurações finais
        if preset:
            if preset not in VOICE_PRESETS:
                raise HTTPException(status_code=400, detail=f"Preset '{preset}' não encontrado")
            
            preset_config = VOICE_PRESETS[preset]
            final_speed = preset_config["length_scale"]
            config_source = f"preset '{preset}'"
        else:
            final_speed = speed if speed is not None else 1.0
            config_source = "manual parameters" if speed is not None else "default values"
        
        # Determinar modelo automaticamente se não especificado
        if model == "auto":
            model_key, model_config = get_model_for_language(lang)
            if not model_key:
                raise HTTPException(status_code=400, detail=f"Language '{lang}' not supported")
        else:
            if model not in MODEL_CONFIG:
                raise HTTPException(status_code=400, detail=f"Model '{model}' not available")
            model_key = model
            model_config = MODEL_CONFIG[model_key]
        
        # Verificar se o idioma é suportado pelo modelo
        if lang not in model_config["supported_languages"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Language '{lang}' not supported by {model_config['name']}",
                    "supported_languages": model_config["supported_languages"]
                }
            )
        
        # Carregar modelo
        tts_model, tts_tokenizer = load_model(model_key)
        
        # Gerar áudio usando MMS-TTS com accelerate
        inputs = tts_tokenizer(text, return_tensors="pt")
        
        with torch.no_grad():
            if accelerator.mixed_precision != "no":
                with accelerator.autocast():
                    output = tts_model(**inputs)
            else:
                output = tts_model(**inputs)
            
            # Extrair tensor de áudio
            if hasattr(output, 'waveform'):
                audio_tensor = output.waveform
            elif hasattr(output, 'audio'):
                audio_tensor = output.audio
            else:
                audio_tensor = output
        
        # Converter para numpy
        audio = audio_tensor.cpu().float().numpy().squeeze()
        
        # Aplicar ajuste de velocidade se necessário
        if final_speed != 1.0:
            try:
                import librosa
                audio = librosa.effects.time_stretch(audio, rate=1.0/final_speed)
                logger.info(f"Applied speed adjustment: {final_speed}")
            except ImportError:
                logger.warning("librosa not available, speed adjustment skipped")
                final_speed = 1.0
        
        # Obter sample rate do modelo
        sample_rate = getattr(tts_model.config, 'sampling_rate', 22050)
        
        # Salvar arquivo temporário
        temp_id = uuid.uuid4().hex
        temp_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        wav_path = os.path.join(temp_dir, f"tts_{temp_id}.wav")
        mp3_path = os.path.join(temp_dir, f"tts_{temp_id}.mp3")
        
        # Salvar como WAV
        write(wav_path, sample_rate, (audio * 32767).astype(np.int16))
        
        # Converter para MP3
        audio_segment = AudioSegment.from_wav(wav_path)
        audio_segment.export(mp3_path, format="mp3", bitrate="128k")
        
        # Limpar arquivo WAV temporário
        os.remove(wav_path)
        
        logger.info(f"Generated audio for user {current_user.get('name')}: '{text}' ({lang}) - speed:{final_speed}")
        
        return FileResponse(
            mp3_path, 
            media_type="audio/mpeg", 
            filename=f"tts_{lang}_{temp_id}.mp3",
            headers={
                "X-Model-Used": model_config["name"],
                "X-Language": model_config["supported_languages"][lang],
                "X-Voice-Config": f"speed:{final_speed}",
                "X-Config-Source": config_source,
                "X-User": current_user.get("name", "Unknown"),
                "X-Auth-Type": current_user.get("type", "unknown")
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating audio for user {current_user.get('name')}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check(current_user: dict = Depends(get_current_active_user)):
    """Health check protegido"""
    return {
        "status": "ok", 
        "message": "Hebrew & Greek TTS API is running (Authenticated)",
        "user": current_user.get("name", "Unknown"),
        "device": str(device),
        "loaded_models": list(models.keys()),
        "supported_languages": ["heb", "ell", "por"]
    }

@app.get("/models")
def get_models(current_user: dict = Depends(get_current_active_user)):
    """Lista modelos (protegido)"""
    return {
        "models": MODEL_CONFIG,
        "total_models": len(MODEL_CONFIG),
        "user": current_user.get("name")
    }

@app.get("/languages") 
def get_supported_languages(current_user: dict = Depends(get_current_active_user)):
    """Lista idiomas (protegido)"""
    all_languages = {}
    for model_key, config in MODEL_CONFIG.items():
        for lang_code, lang_name in config["supported_languages"].items():
            all_languages[lang_code] = {
                "name": lang_name,
                "model": config["name"],
                "model_key": model_key
            }
    
    return {
        "supported_languages": all_languages,
        "total_languages": len(all_languages),
        "user": current_user.get("name")
    }

@app.get("/voice-presets")
def get_voice_presets(current_user: dict = Depends(get_current_active_user)):
    """Lista presets (protegido)"""
    return {
        "presets": VOICE_PRESETS,
        "user": current_user.get("name"),
        "note": "MMS-TTS models have limited parameter support."
    }

# ============================================
# ROTAS ADMINISTRATIVAS
# ============================================

@app.get("/admin/users")
def list_active_users(admin_user: dict = Depends(get_admin_user)):
    """Lista usuários ativos (apenas admin)"""
    # Em produção, consultar banco de dados
    return {
        "active_sessions": len(request_counts),
        "admin": admin_user.get("name"),
        "rate_limits": dict(list(request_counts.items())[:10])  # Apenas uma amostra
    }

@app.post("/admin/generate-api-key")
def generate_api_key(
    name: str = Form(...),
    permissions: str = Form(default="tts,models"),
    rate_limit: int = Form(default=100),
    admin_user: dict = Depends(get_admin_user)
):
    """Gera nova API key (apenas admin)"""
    import secrets
    
    new_key = f"tts-{secrets.token_urlsafe(32)}"
    
    # Em produção, salvar em banco de dados
    API_KEYS[new_key] = {
        "name": name,
        "permissions": permissions.split(","),
        "rate_limit": rate_limit,
        "active": True,
        "created_by": admin_user.get("name"),
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {
        "api_key": new_key,
        "name": name,
        "permissions": permissions.split(","),
        "rate_limit": rate_limit,
        "created_by": admin_user.get("name")
    }

@app.post("/admin/create-user")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    permissions: str = Form("tts,models"),
    is_admin: bool = Form(False),
    rate_limit: int = Form(100),
    admin_user: dict = Depends(get_admin_user)
):
    """Cria novo usuário (apenas admin)"""
    try:
        permissions_list = [p.strip() for p in permissions.split(",")]
        
        user_id = db_manager.create_user(
            username=username,
            password=password,
            email=email,
            permissions=permissions_list,
            is_admin=is_admin,
            rate_limit=rate_limit
        )
        
        return {
            "message": f"User {username} created successfully",
            "user_id": user_id,
            "created_by": admin_user.get("username", admin_user.get("name"))
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/admin/create-api-key")
def create_api_key(
    request: Request,
    name: str = Form(...),
    permissions: str = Form("tts,models"),
    rate_limit: int = Form(100),
    expires_days: int = Form(None),
    admin_user: dict = Depends(get_admin_user)
):
    """Cria nova API key (apenas admin)"""
    try:
        permissions_list = [p.strip() for p in permissions.split(",")]
        created_by = admin_user.get("user_id") if admin_user["type"] == "jwt" else None
        
        api_key = db_manager.create_api_key(
            name=name,
            permissions=permissions_list,
            rate_limit=rate_limit,
            expires_days=expires_days,
            created_by=created_by
        )
        
        return {
            "message": f"API key '{name}' created successfully",
            "api_key": api_key,
            "name": name,
            "permissions": permissions_list,
            "rate_limit": rate_limit,
            "expires_days": expires_days,
            "created_by": admin_user.get("username", admin_user.get("name")),
            "usage": {
                "header": "X-API-Key",
                "example": f"curl -H 'X-API-Key: {api_key}' https://your-api.com/speak"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/init-default-data")
def initialize_default_data(admin_user: dict = Depends(get_admin_user)):
    """Inicializa dados padrão com configuração via env vars (apenas admin)"""
    try:
        result = db_manager.initialize_default_data()
        
        # Não retornar senhas em produção
        if os.getenv("ENVIRONMENT", "production") == "production":
            # Limpar informações sensíveis
            if "admin_user" in result and "credentials" in result["admin_user"]:
                result["admin_user"]["credentials"] = "*** HIDDEN IN PRODUCTION ***"
            if "demo_user" in result and "credentials" in result["demo_user"]:
                result["demo_user"]["credentials"] = "*** HIDDEN IN PRODUCTION ***"
            if "demo_api_key" in result and "key" in result["demo_api_key"]:
                key = result["demo_api_key"]["key"]
                result["demo_api_key"]["key"] = f"{key[:8]}...{key[-4:]}"
            if "admin_api_key" in result and "key" in result["admin_api_key"]:
                key = result["admin_api_key"]["key"]
                result["admin_api_key"]["key"] = f"{key[:8]}...{key[-4:]}"
        
        return {
            "message": "Default data initialization completed",
            "initiated_by": admin_user.get("username", admin_user.get("name")),
            "results": result
        }
        
    except Exception as e:
        logger.error(f"Error initializing default data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/system-info")
def get_system_info(admin_user: dict = Depends(get_admin_user)):
    """Informações do sistema (apenas admin)"""
    with db_manager.get_connection() as conn:
        # Estatísticas de usuários
        users_count = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
        active_users = conn.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1").fetchone()["count"]
        
        # Estatísticas de API keys
        api_keys_count = conn.execute("SELECT COUNT(*) as count FROM api_keys").fetchone()["count"]
        active_keys = conn.execute("SELECT COUNT(*) as count FROM api_keys WHERE is_active = 1").fetchone()["count"]
        
        # Estatísticas de sessões
        active_sessions = conn.execute("SELECT COUNT(*) as count FROM sessions WHERE is_revoked = 0 AND expires_at > CURRENT_TIMESTAMP").fetchone()["count"]
        
        # Logs recentes
        recent_logs = conn.execute("""
            SELECT action, COUNT(*) as count 
            FROM audit_logs 
            WHERE timestamp > datetime('now', '-24 hours')
            GROUP BY action
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()
    
    return {
        "database": {
            "path": db_manager.db_path,
            "exists": os.path.exists(db_manager.db_path),
            "size_mb": round(os.path.getsize(db_manager.db_path) / (1024*1024), 2) if os.path.exists(db_manager.db_path) else 0
        },
        "statistics": {
            "users": {"total": users_count, "active": active_users},
            "api_keys": {"total": api_keys_count, "active": active_keys},
            "active_sessions": active_sessions
        },
        "recent_activity": [{"action": log["action"], "count": log["count"]} for log in recent_logs],
        "configuration": {
            "auto_init_enabled": os.getenv("AUTO_INIT_DEFAULT_DATA", "false"),
            "environment": os.getenv("ENVIRONMENT", "production"),
            "jwt_expire_minutes": ACCESS_TOKEN_EXPIRE_MINUTES
        }
    }

# Manter o código existente para desenvolvimento local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

