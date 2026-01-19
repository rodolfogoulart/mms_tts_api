# ============================================
# IMPORTS PRINCIPAIS
# ============================================
from fastapi import FastAPI, Form, HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

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
import hashlib
import logging  # ← IMPORTANTE: Este import estava faltando ou na posição errada
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
# CONFIGURAÇÃO DE LOGGING (LOGO APÓS OS IMPORTS)
# ============================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Configuração de limite de modelos em memória
MAX_LOADED_MODELS = int(os.getenv("MAX_LOADED_MODELS", "2"))
logger.info(f"Max loaded models: {MAX_LOADED_MODELS}")

# Classe para rastrear uso dos modelos
class ModelWrapper:
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
        self.last_used = time.time()
        self.usage_count = 0
    
    def mark_used(self):
        self.last_used = time.time()
        self.usage_count += 1

# Modelos carregados dinamicamente
models = {}

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
    # Se modelo já está carregado, atualizar uso e retornar
    if model_key in models:
        models[model_key].mark_used()
        logger.info(f"Model cache HIT: {model_key} (used {models[model_key].usage_count} times)")
        return models[model_key].model, models[model_key].tokenizer
    
    # Verificar se precisa descarregar modelo menos usado
    if len(models) >= MAX_LOADED_MODELS:
        # Encontrar modelo menos usado recentemente
        least_used_key = min(models.keys(), key=lambda k: models[k].last_used)
        least_used = models[least_used_key]
        
        logger.info(f"Unloading model '{least_used_key}' (used {least_used.usage_count} times, last: {time.time() - least_used.last_used:.0f}s ago)")
        
        # Remover referências
        del models[least_used_key]
        
        # Liberar memória
        if has_cuda:
            torch.cuda.empty_cache()
        import gc
        gc.collect()
        
        logger.info(f"Model '{least_used_key}' unloaded, memory freed")
    
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
    
    # Criar wrapper e armazenar
    wrapper = ModelWrapper(model, tokenizer)
    models[model_key] = wrapper
    
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
                    if "demo_api_key" in result and "key" in result["demo_api_key"]:
                        logger.info(f"Demo API Key: {result['demo_api_key']['key']}")
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
    background_tasks: BackgroundTasks,
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
    # Adicionar validação
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    # Limitar tamanho do texto
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 characters)")
    
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
        
        # ====== VERIFICAR CACHE ======
        cache_entry = db_manager.get_cache_entry(text, lang, model_key, final_speed)
        if cache_entry:
            logger.info(f"Returning cached audio for user {current_user.get('name')}: '{text[:50]}...' (hit #{cache_entry['hit_count']})")
            return FileResponse(
                cache_entry['file_path'], 
                media_type="audio/mpeg", 
                filename=f"tts_{lang}_{os.path.basename(cache_entry['file_path'])}",
                headers={
                    "X-Model-Used": model_config["name"],
                    "X-Language": model_config["supported_languages"][lang],
                    "X-Voice-Config": f"speed:{final_speed}",
                    "X-Config-Source": config_source,
                    "X-User": current_user.get("name", "Unknown"),
                    "X-Auth-Type": current_user.get("type", "unknown"),
                    "X-Cache-Hit": "true",
                    "X-Cache-Hits": str(cache_entry['hit_count'])
                }
            )
        
        # ====== GERAR ÁUDIO (CACHE MISS) ======
        logger.info(f"Cache MISS - Generating new audio: '{text[:50]}...'")
        
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
        
        # Criar diretórios de cache
        cache_dir = os.path.join(os.getcwd(), "cache")
        temp_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)
        
        # Gerar ID único para o cache
        cache_id = hashlib.sha256(f"{text}{lang}{model_key}{final_speed}".encode()).hexdigest()[:16]
        
        wav_path = os.path.join(temp_dir, f"tts_{cache_id}.wav")
        mp3_path = os.path.join(cache_dir, f"tts_{cache_id}.mp3")
        
        # Salvar como WAV
        write(wav_path, sample_rate, (audio * 32767).astype(np.int16))
        
        # Converter para MP3
        audio_segment = AudioSegment.from_wav(wav_path)
        audio_segment.export(mp3_path, format="mp3", bitrate="128k")
        
        # Limpar arquivo WAV temporário
        os.remove(wav_path)
        
        # Salvar no cache do banco de dados
        file_size = os.path.getsize(mp3_path)
        db_manager.save_cache_entry(text, lang, model_key, final_speed, mp3_path, file_size)
        
        logger.info(f"Generated audio for user {current_user.get('name')}: '{text}' ({lang}) - speed:{final_speed} - {config_source}")
        
        return FileResponse(
            mp3_path, 
            media_type="audio/mpeg", 
            filename=f"tts_{lang}_{cache_id}.mp3",
            headers={
                "X-Model-Used": model_config["name"],
                "X-Language": model_config["supported_languages"][lang],
                "X-Voice-Config": f"speed:{final_speed}",
                "X-Config-Source": config_source,
                "X-User": current_user.get("name", "Unknown"),
                "X-Auth-Type": current_user.get("type", "unknown"),
                "X-Cache-Hit": "false"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating audio for user {current_user.get('name')}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """Health check público (sem autenticação)"""
    return {
        "status": "healthy", 
        "message": "Hebrew & Greek TTS API is running",
        "version": "2.1.0",
        "device": str(device),
        "loaded_models": list(models.keys()),
        "supported_languages": ["heb", "ell", "por"],
        "authentication": "required for protected endpoints"
    }

@app.get("/health/detailed")
def health_check_detailed(current_user: dict = Depends(get_current_active_user)):
    """Health check detalhado (protegido)"""
    return {
        "status": "healthy", 
        "message": "Hebrew & Greek TTS API is running (Authenticated)",
        "user": current_user.get("name", "Unknown"),
        "device": str(device),
        "loaded_models": list(models.keys()),
        "supported_languages": ["heb", "ell", "por"],
        "rate_limit_info": {
            "current": current_user.get("rate_limit_current", 0),
            "max": current_user.get("rate_limit_max", 100)
        }
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
    with db_manager.get_connection() as conn:
        active_sessions = conn.execute(
            "SELECT COUNT(*) as count FROM sessions WHERE is_revoked = 0 AND expires_at > CURRENT_TIMESTAMP"
        ).fetchone()["count"]
        
        active_users = conn.execute("""
            SELECT id, username, email, rate_limit, is_admin, created_at, last_login
            FROM users WHERE is_active = 1
        """).fetchall()
    
    return {
        "active_sessions": active_sessions,
        "active_users": [dict(user) for user in active_users],
        "admin": admin_user.get("username", admin_user.get("name"))
    }

@app.post("/admin/generate-api-key")
def generate_api_key(
    name: str = Form(...),
    permissions: str = Form(default="tts,models"),
    rate_limit: int = Form(default=100),
    expires_days: int = Form(default=None),
    admin_user: dict = Depends(get_admin_user)
):
    """Gera nova API key (apenas admin)"""
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
def initialize_default_data_route(admin_user: dict = Depends(get_admin_user)):
    """Inicializa dados padrão com configuração via env vars (apenas admin)"""
    try:
        result = db_manager.initialize_default_data()
        
        # Não retornar senhas em produção
        if os.getenv("ENVIRONMENT", "production") == "production":
            # Limpar informações sensíveis
            if result and "admin_user" in result and "credentials" in result["admin_user"]:
                result["admin_user"]["credentials"] = "*** HIDDEN IN PRODUCTION ***"
            if result and "demo_user" in result and "credentials" in result["demo_user"]:
                result["demo_user"]["credentials"] = "*** HIDDEN IN PRODUCTION ***"
            if result and "demo_api_key" in result and "key" in result["demo_api_key"]:
                key = result["demo_api_key"]["key"]
                result["demo_api_key"]["key"] = f"{key[:8]}...{key[-4:]}"
            if result and "admin_api_key" in result and "key" in result["admin_api_key"]:
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

@app.delete("/admin/revoke-api-key/{key_id}")
def revoke_api_key(
    key_id: int,
    admin_user: dict = Depends(get_admin_user)
):
    """Revoga API key (apenas admin)"""
    with db_manager.get_connection() as conn:
        conn.execute(
            "UPDATE api_keys SET is_active = 0 WHERE id = ?",
            (key_id,)
        )
        conn.commit()
    
    return {"message": f"API key {key_id} revoked"}

@app.get("/admin/cache/stats")
def get_cache_stats(admin_user: dict = Depends(get_admin_user)):
    """Estatísticas do cache (apenas admin)"""
    stats = db_manager.get_cache_stats()
    return {
        "cache_stats": stats,
        "max_size_mb": 100,
        "usage_percentage": round((stats['total_size_mb'] / 100) * 100, 2) if stats['total_size_mb'] else 0,
        "admin": admin_user.get("username", admin_user.get("name"))
    }

@app.post("/admin/cache/cleanup")
def force_cache_cleanup(admin_user: dict = Depends(get_admin_user)):
    """Força limpeza do cache (apenas admin)"""
    result = db_manager.cleanup_cache(max_size_mb=100)
    return {
        "message": "Cache cleanup executed",
        "result": result,
        "admin": admin_user.get("username", admin_user.get("name"))
    }

@app.delete("/admin/cache/clear")
def clear_all_cache(admin_user: dict = Depends(get_admin_user)):
    """Limpa todo o cache (apenas admin)"""
    try:
        with db_manager.get_connection() as conn:
            # Buscar todos os arquivos
            entries = conn.execute('SELECT file_path FROM tts_cache').fetchall()
            
            removed_count = 0
            for entry in entries:
                if os.path.exists(entry['file_path']):
                    try:
                        os.remove(entry['file_path'])
                        removed_count += 1
                    except Exception as e:
                        logger.error(f"Error removing {entry['file_path']}: {e}")
            
            # Limpar tabela
            conn.execute('DELETE FROM tts_cache')
            conn.commit()
        
        return {
            "message": "All cache cleared",
            "files_removed": removed_count,
            "admin": admin_user.get("username", admin_user.get("name"))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/models/loaded")
def get_loaded_models(admin_user: dict = Depends(get_admin_user)):
    """Lista modelos carregados em memória (apenas admin)"""
    loaded = []
    for key, wrapper in models.items():
        model_info = MODEL_CONFIG.get(key, {})
        loaded.append({
            "key": key,
            "name": model_info.get("name", key),
            "usage_count": wrapper.usage_count,
            "last_used_seconds_ago": int(time.time() - wrapper.last_used),
            "languages": list(model_info.get("supported_languages", {}).keys())
        })
    
    # Ordenar por uso
    loaded.sort(key=lambda x: x["usage_count"], reverse=True)
    
    return {
        "loaded_models": loaded,
        "total_loaded": len(loaded),
        "max_models": MAX_LOADED_MODELS,
        "available_models": list(MODEL_CONFIG.keys()),
        "admin": admin_user.get("username", admin_user.get("name"))
    }

@app.post("/admin/models/unload/{model_key}")
def unload_model(model_key: str, admin_user: dict = Depends(get_admin_user)):
    """Descarrega modelo específico da memória (apenas admin)"""
    if model_key not in models:
        raise HTTPException(status_code=404, detail=f"Model '{model_key}' not loaded")
    
    wrapper = models[model_key]
    usage_info = {
        "usage_count": wrapper.usage_count,
        "last_used_seconds_ago": int(time.time() - wrapper.last_used)
    }
    
    del models[model_key]
    
    # Liberar memória
    if has_cuda:
        torch.cuda.empty_cache()
    import gc
    gc.collect()
    
    return {
        "message": f"Model '{model_key}' unloaded",
        "usage_info": usage_info,
        "admin": admin_user.get("username", admin_user.get("name"))
    }

def cleanup_old_temp_files():
    """Remove arquivos temporários antigos (> 1 hora)"""
    temp_dir = os.path.join(os.getcwd(), "temp")
    if not os.path.exists(temp_dir):
        return
    
    now = time.time()
    for filename in os.listdir(temp_dir):
        filepath = os.path.join(temp_dir, filename)
        if os.path.getmtime(filepath) < now - 3600:  # 1 hora
            try:
                os.remove(filepath)
                logger.info(f"Removed old temp file: {filename}")
            except Exception as e:
                logger.error(f"Error removing {filename}: {e}")

def cleanup_cache_if_needed():
    """Verifica e limpa cache se ultrapassar 100MB"""
    try:
        result = db_manager.cleanup_cache(max_size_mb=100)
        if result['cleaned']:
            logger.info(f"Cache cleanup: removed {result['removed_count']} entries, freed {result['freed_mb']}MB")
    except Exception as e:
        logger.error(f"Error during cache cleanup: {e}")

# Agendar limpeza a cada 30 minutos
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_old_temp_files, 'interval', minutes=30)
scheduler.add_job(cleanup_cache_if_needed, 'interval', minutes=30)
scheduler.start()

# Manter o código existente para desenvolvimento local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

