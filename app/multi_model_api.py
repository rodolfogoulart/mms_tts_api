#!/usr/bin/env python3
"""
MMS-TTS API Implementation using Sherpa-ONNX
This fixes the audio quality issues by using proper Sherpa-ONNX inference
instead of raw ONNX Runtime.
"""

from fastapi import FastAPI, Form, HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

# Sherpa-ONNX for TTS
import sherpa_onnx
from scipy.io.wavfile import write
from pydub import AudioSegment
from huggingface_hub import hf_hub_download
import json

# Standard imports
import numpy as np
import os
import uuid
import hashlib
import logging
import time
import shutil
from datetime import datetime
from pathlib import Path

# Auth system
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

# Monitoring router
try:
    from .monitoring import router as monitoring_router
except ImportError:
    monitoring_router = None

# ============================================
# LOGGING CONFIGURATION
# ============================================
logging.basicConfig(level=logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Word alignment for forced alignment
try:
    from .word_alignment import forced_align_audio_to_text, init_mfa
    WORD_ALIGNMENT_AVAILABLE = True
except ImportError:
    WORD_ALIGNMENT_AVAILABLE = False
    logger.warning("⚠️  Word alignment module not available")

# ============================================
# APPLICATION CONFIGURATION
# ============================================
app = FastAPI(
    title="MMS-TTS API with Sherpa-ONNX", 
    description="Multilingual TTS API using Sherpa-ONNX for proper audio quality",
    version="4.0.0-sherpa"
)

templates = Jinja2Templates(directory="app/templates")

# ============================================
# MIDDLEWARES
# ============================================
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if monitoring_router:
    app.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])

# ============================================
# SHERPA-ONNX MODEL CONFIGURATION
# ============================================

MAX_LOADED_MODELS = int(os.getenv("MAX_LOADED_MODELS", "2"))
logger.info(f"Max loaded models: {MAX_LOADED_MODELS}")

class SherpaONNXModel:
    """Wrapper for Sherpa-ONNX TTS instance"""
    def __init__(self, tts_instance, lang_code):
        self.tts = tts_instance
        self.lang_code = lang_code
        self.sample_rate = tts_instance.sample_rate
        self.num_speakers = tts_instance.num_speakers
        self.last_used = time.time()
        self.usage_count = 0
    
    def mark_used(self):
        self.last_used = time.time()
        self.usage_count += 1
    
    def generate(self, text: str, sid: int = 0, speed: float = 1.0):
        """Generate speech using Sherpa-ONNX"""
        self.mark_used()
        audio = self.tts.generate(text, sid=sid, speed=speed)
        return audio.samples, audio.sample_rate

# Store loaded models
models = {}

# Model configurations
MODEL_CONFIG = {
    "hebrew": {
        "name": "MMS-TTS Hebrew (Sherpa-ONNX)",
        "model_id": "willwade/mms-tts-multilingual-models-onnx",
        "type": "mms-sherpa-onnx",
        "lang_code": "heb",
        "supported_languages": {"heb": "Hebrew"}
    },
    "greek": {
        "name": "MMS-TTS Greek (Sherpa-ONNX)", 
        "model_id": "willwade/mms-tts-multilingual-models-onnx",
        "type": "mms-sherpa-onnx",
        "lang_code": "ell",
        "supported_languages": {"ell": "Greek"}
    },
    "portuguese": {
        "name": "MMS-TTS Portuguese (Sherpa-ONNX)",
        "model_id": "willwade/mms-tts-multilingual-models-onnx",
        "type": "mms-sherpa-onnx",
        "lang_code": "por",
        "supported_languages": {"por": "Portuguese"}
    },
}

VOICE_PRESETS = {
    "natural": {"description": "Natural balanced voice", "speed": 1.0},
    "expressive": {"description": "Slightly slower (more expressive)", "speed": 0.9},
    "calm": {"description": "Calm and slower", "speed": 0.8},
    "fast": {"description": "Faster speech", "speed": 1.2},
    "slow": {"description": "Very slow and clear", "speed": 0.7}
}

# ============================================
# MODEL LOADING WITH SHERPA-ONNX
# ============================================

def download_sherpa_onnx_model(lang_code: str):
    """Download model and tokens files for Sherpa-ONNX"""
    model_id = "willwade/mms-tts-multilingual-models-onnx"
    cache_dir = ".cache/onnx_models"
    
    try:
        model_path = hf_hub_download(
            repo_id=model_id,
            filename=f"{lang_code}/model.onnx",
            cache_dir=cache_dir
        )
        tokens_path = hf_hub_download(
            repo_id=model_id,
            filename=f"{lang_code}/tokens.txt",
            cache_dir=cache_dir
        )
        logger.info(f"Downloaded {lang_code}: model={model_path}, tokens={tokens_path}")
        return model_path, tokens_path
    except Exception as e:
        logger.error(f"Failed to download {lang_code} model: {e}")
        raise

def load_sherpa_onnx_model(model_name: str):
    """Load a Sherpa-ONNX TTS model"""
    if model_name in models:
        logger.info(f"Model {model_name} already loaded")
        models[model_name].mark_used()
        return models[model_name]
    
    # Unload least recently used model if at capacity
    if len(models) >= MAX_LOADED_MODELS:
        lru_model = min(models.items(), key=lambda x: x[1].last_used)
        logger.info(f"Unloading LRU model: {lru_model[0]}")
        del models[lru_model[0]]
    
    config = MODEL_CONFIG.get(model_name)
    if not config:
        raise ValueError(f"Unknown model: {model_name}")
    
    lang_code = config["lang_code"]
    
    # Download model files
    model_path, tokens_path = download_sherpa_onnx_model(lang_code)
    
    # Configure Sherpa-ONNX
    vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
        model=str(model_path),
        tokens=str(tokens_path),
        length_scale=1.0,
        noise_scale=0.667,
        noise_scale_w=0.8,
    )
    
    model_config = sherpa_onnx.OfflineTtsModelConfig(
        vits=vits_config,
        num_threads=2,
        debug=False,
        provider="cpu",
    )
    
    tts_config = sherpa_onnx.OfflineTtsConfig(
        model=model_config,
        max_num_sentences=1,
    )
    
    logger.info(f"Loading Sherpa-ONNX model: {model_name} ({lang_code})")
    start = time.time()
    
    try:
        tts_instance = sherpa_onnx.OfflineTts(tts_config)
        elapsed = time.time() - start
        
        logger.info(f"Model loaded in {elapsed:.2f}s")
        logger.info(f"  Sample rate: {tts_instance.sample_rate}")
        logger.info(f"  Num speakers: {tts_instance.num_speakers}")
        
        wrapper = SherpaONNXModel(tts_instance, lang_code)
        models[model_name] = wrapper
        return wrapper
        
    except Exception as e:
        logger.error(f"Failed to load Sherpa-ONNX model {model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load model: {e}")

# ============================================
# CACHE MANAGEMENT
# ============================================

CACHE_DIR = "cache"
TEMP_DIR = "temp"
MAX_CACHE_SIZE_MB = int(os.getenv("MAX_CACHE_SIZE_MB", "500"))

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def get_cache_key(text: str, model_name: str, speed: float, output_format: str) -> str:
    """Generate cache key from parameters"""
    content = f"{text}_{model_name}_{speed}_{output_format}"
    return hashlib.md5(content.encode()).hexdigest()[:16]

def cleanup_old_cache():
    """Remove old cached files"""
    try:
        cache_files = []
        for f in os.listdir(CACHE_DIR):
            path = os.path.join(CACHE_DIR, f)
            if os.path.isfile(path):
                cache_files.append((path, os.path.getmtime(path), os.path.getsize(path)))
        
        # Sort by modification time (oldest first)
        cache_files.sort(key=lambda x: x[1])
        
        total_size_mb = sum(f[2] for f in cache_files) / (1024 * 1024)
        
        if total_size_mb > MAX_CACHE_SIZE_MB:
            removed = 0
            for path, _, size in cache_files:
                if total_size_mb <= MAX_CACHE_SIZE_MB * 0.8:  # Keep 80% threshold
                    break
                try:
                    os.remove(path)
                    total_size_mb -= size / (1024 * 1024)
                    removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove {path}: {e}")
            
            logger.info(f"Cleaned up {removed} old cache files")
    except Exception as e:
        logger.error(f"Cache cleanup error: {e}")

# Schedule cache cleanup
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_old_cache, 'interval', hours=1)
scheduler.start()

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Landing page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "4.0.0-sherpa",
        "loaded_models": list(models.keys()),
        "engine": "sherpa-onnx"
    }

# ============================================
# AUTH ENDPOINTS
# ============================================

@app.post("/auth/login")
def login(
    request: Request,
    username: str = Form(...), 
    password: str = Form(...)
):
    """Login with username/password (returns JWT token)"""
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
    """Logout (revokes JWT token)"""
    if current_user["type"] == "jwt" and "jti" in current_user:
        revoke_token(current_user["jti"])
        return {"message": "Successfully logged out"}
    
    return {"message": "No active session to logout"}

@app.get("/auth/me")
def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """Get current user information"""
    stats = {}
    if current_user["type"] == "jwt" and "user_id" in current_user:
        stats = db_manager.get_user_stats(current_user["user_id"])
    
    return {
        "user": current_user,
        "authenticated": True,
        "stats": stats
    }

# ============================================
# TTS ENDPOINTS
# ============================================

@app.post("/speak")
async def speak(
    text: str = Form(...),
    model: str = Form("hebrew"),
    speed: float = Form(1.0),
    output_format: str = Form("mp3"),
    user = Depends(get_rate_limited_user)
):
    """
    Generate speech from text using Sherpa-ONNX
    
    - **text**: Text to convert to speech
    - **model**: Model to use (hebrew, greek, portuguese)
    - **speed**: Speech speed (0.5-2.0, default 1.0)
    - **output_format**: Output format (mp3 or wav)
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if model not in MODEL_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model}")
    
    if not (0.5 <= speed <= 2.0):
        raise HTTPException(status_code=400, detail="Speed must be between 0.5 and 2.0")
    
    if output_format not in ["mp3", "wav"]:
        raise HTTPException(status_code=400, detail="Format must be mp3 or wav")
    
    # Check cache
    cache_key = get_cache_key(text, model, speed, output_format)
    cache_file = os.path.join(CACHE_DIR, f"tts_{cache_key}.{output_format}")
    
    if os.path.exists(cache_file):
        logger.info(f"Cache hit: {cache_key}")
        return FileResponse(
            cache_file,
            media_type="audio/mpeg" if output_format == "mp3" else "audio/wav",
            filename=f"speech.{output_format}"
        )
    
    # Load model
    try:
        model_wrapper = load_sherpa_onnx_model(model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Generate speech
    try:
        start = time.time()
        audio_samples, sample_rate = model_wrapper.generate(text, sid=0, speed=speed)
        elapsed = time.time() - start
        
        duration = len(audio_samples) / sample_rate
        rtf = elapsed / duration if duration > 0 else 0
        
        logger.info(f"Generated {duration:.2f}s audio in {elapsed:.2f}s (RTF: {rtf:.2f}x)")
        logger.info(f"Audio array shape: {audio_samples.shape if hasattr(audio_samples, 'shape') else len(audio_samples)}, dtype: {audio_samples.dtype if hasattr(audio_samples, 'dtype') else type(audio_samples)}, sample_rate: {sample_rate}")
        
        # Convert to numpy array if it's a list
        if not isinstance(audio_samples, np.ndarray):
            audio_samples = np.array(audio_samples, dtype=np.float32)
            logger.info(f"Converted list to numpy array: {audio_samples.shape}")
        
        # Save temporary WAV
        temp_wav = os.path.join(TEMP_DIR, f"{uuid.uuid4()}.wav")
        
        # Ensure audio is 1D array
        if len(audio_samples.shape) > 1:
            audio_samples = audio_samples.flatten()
        
        # Convert float32 to int16
        audio_int16 = np.int16(np.clip(audio_samples * 32767, -32768, 32767))
        logger.info(f"Converted audio size: {len(audio_int16)} samples, {len(audio_int16) * 2 / 1024:.2f} KB raw")
        write(temp_wav, sample_rate, audio_int16)
        
        # Convert to output format
        if output_format == "mp3":
            audio_segment = AudioSegment.from_wav(temp_wav)
            logger.info(f"WAV temp file size: {os.path.getsize(temp_wav) / 1024:.2f} KB")
            audio_segment.export(cache_file, format="mp3", bitrate="128k")
            logger.info(f"MP3 final file size: {os.path.getsize(cache_file) / 1024:.2f} KB")
            os.remove(temp_wav)
        else:
            shutil.move(temp_wav, cache_file)
            logger.info(f"WAV final file size: {os.path.getsize(cache_file) / 1024:.2f} KB")
        
        return FileResponse(
            cache_file,
            media_type="audio/mpeg" if output_format == "mp3" else "audio/wav",
            filename=f"speech.{output_format}"
        )
        
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")


@app.post("/speak_sync")
async def speak_with_word_alignment(
    text: str = Form(...),
    model: str = Form("hebrew"),
    speed: float = Form(1.0),
    output_format: str = Form("mp3"),
    return_audio: bool = Form(True),
    user = Depends(get_rate_limited_user)
):
    """
    Generate speech with word-level timestamps (FORCED ALIGNMENT)
    
    Este endpoint:
    1. Gera áudio via MMS-TTS (Sherpa-ONNX)
    2. Executa forced alignment via Whisper (timestamps palavra-por-palavra)
    3. Retorna JSON com áudio + timestamps alinhados ao texto original
    
    O texto fornecido é a ÚNICA FONTE DA VERDADE.
    O Whisper é usado APENAS para obter timestamps, não para reconhecimento.
    
    Args:
    - **text**: Texto original (hebraico, grego ou português)
    - **model**: Modelo TTS (hebrew, greek, portuguese)
    - **speed**: Velocidade da fala (0.5-2.0)
    - **output_format**: Formato do áudio (mp3 ou wav)
    - **return_audio**: Se True, inclui áudio base64 no JSON
    
    Returns:
        JSON com estrutura:
        {
            "text": str,              # Texto original
            "model": str,             # Modelo usado
            "speed": float,           # Velocidade
            "audio_duration": float,  # Duração em segundos
            "audio_file": str,        # Nome do arquivo (se return_audio=False)
            "audio_base64": str,      # Áudio em base64 (se return_audio=True)
            "word_timestamps": [      # Timestamps por palavra
                {
                    "text": str,      # Palavra original
                    "start": float,   # Timestamp início (segundos)
                    "end": float,     # Timestamp fim (segundos)
                    "textStart": int, # Posição no texto original (char index)
                    "textEnd": int,   # Posição fim no texto
                    "confidence": float # Confiança do alinhamento (0-1)
                }
            ],
            "alignment_stats": {
                "total_words": int,
                "matched_words": int,
                "match_ratio": float
            }
        }
    """
    if not WORD_ALIGNMENT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Word alignment feature not available. Install faster-whisper first."
        )
    
    # Validações
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if model not in MODEL_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model}")
    
    if not (0.5 <= speed <= 2.0):
        raise HTTPException(status_code=400, detail="Speed must be between 0.5 and 2.0")
    
    if output_format not in ["mp3", "wav"]:
        raise HTTPException(status_code=400, detail="Format must be mp3 or wav")
    
    # Mapa de modelo -> código de idioma Whisper
    LANGUAGE_MAP = {
        "hebrew": "he",
        "greek": "el",
        "portuguese": "pt"
    }
    whisper_lang = LANGUAGE_MAP.get(model, "he")
    
    logger.info(f"🎯 Forced alignment request: model={model}, lang={whisper_lang}, speed={speed}")
    logger.info(f"   Text: '{text[:50]}...' ({len(text)} chars)")
    
    try:
        # 1. Carregar modelo TTS
        model_wrapper = load_sherpa_onnx_model(model)
        
        # 2. Gerar áudio via Sherpa-ONNX
        start_tts = time.time()
        audio_samples, sample_rate = model_wrapper.generate(text, sid=0, speed=speed)
        elapsed_tts = time.time() - start_tts
        
        # Converter para numpy se necessário
        if not isinstance(audio_samples, np.ndarray):
            audio_samples = np.array(audio_samples, dtype=np.float32)
        
        # Garantir 1D array
        if len(audio_samples.shape) > 1:
            audio_samples = audio_samples.flatten()
        
        # Salvar áudio temporário (WAV para Whisper)
        temp_wav = os.path.join(TEMP_DIR, f"{uuid.uuid4()}.wav")
        audio_int16 = np.int16(np.clip(audio_samples * 32767, -32768, 32767))
        write(temp_wav, sample_rate, audio_int16)
        
        audio_duration = len(audio_samples) / sample_rate
        rtf_tts = elapsed_tts / audio_duration if audio_duration > 0 else 0
        
        logger.info(f"✅ TTS: {audio_duration:.2f}s audio in {elapsed_tts:.2f}s (RTF: {rtf_tts:.2f}x)")
        
        # 3. Executar FORCED ALIGNMENT
        start_align = time.time()
        word_timestamps, audio_dur = forced_align_audio_to_text(
            audio_path=temp_wav,
            original_text=text,
            language=whisper_lang,
            normalize_audio=True
        )
        elapsed_align = time.time() - start_align
        
        logger.info(f"✅ Alignment: {len(word_timestamps)} words in {elapsed_align:.2f}s")
        
        # 4. Estatísticas de alinhamento
        matched_words = sum(1 for w in word_timestamps if w['confidence'] > 0)
        match_ratio = matched_words / len(word_timestamps) if word_timestamps else 0
        
        alignment_stats = {
            "total_words": len(word_timestamps),
            "matched_words": matched_words,
            "match_ratio": round(match_ratio, 2)
        }
        
        # 5. Preparar resposta
        response_data = {
            "text": text,
            "model": model,
            "speed": speed,
            "audio_duration": round(audio_duration, 2),
            "word_timestamps": word_timestamps,
            "alignment_stats": alignment_stats,
            "processing_time": {
                "tts_seconds": round(elapsed_tts, 2),
                "alignment_seconds": round(elapsed_align, 2),
                "total_seconds": round(elapsed_tts + elapsed_align, 2)
            }
        }
        
        # 6. Converter áudio para formato solicitado
        if output_format == "mp3":
            audio_segment = AudioSegment.from_wav(temp_wav)
            temp_output = os.path.join(TEMP_DIR, f"{uuid.uuid4()}.mp3")
            audio_segment.export(temp_output, format="mp3", bitrate="128k")
            os.remove(temp_wav)  # Remover WAV temporário
            final_audio = temp_output
        else:
            final_audio = temp_wav
        
        # 7. Incluir áudio na resposta
        if return_audio:
            # Ler áudio e converter para base64
            import base64
            with open(final_audio, 'rb') as f:
                audio_bytes = f.read()
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            response_data["audio_base64"] = audio_base64
            response_data["audio_format"] = output_format
            
            # Limpar arquivo temporário
            try:
                os.remove(final_audio)
            except Exception as e:
                logger.warning(f"Failed to remove temp audio: {e}")
        else:
            # Mover para cache
            cache_key = get_cache_key(text, model, speed, output_format)
            cache_file = os.path.join(CACHE_DIR, f"tts_{cache_key}.{output_format}")
            shutil.move(final_audio, cache_file)
            response_data["audio_file"] = f"tts_{cache_key}.{output_format}"
            response_data["audio_url"] = f"/cache/{cache_key}"
        
        total_time = elapsed_tts + elapsed_align
        logger.info(f"✅ Total processing: {total_time:.2f}s (TTS: {elapsed_tts:.2f}s + Alignment: {elapsed_align:.2f}s)")
        logger.info(f"   Alignment quality: {match_ratio:.1%} ({matched_words}/{len(word_timestamps)} words)")
        
        return response_data
        
    except Exception as e:
        logger.error(f"❌ Forced alignment failed: {e}")
        # Limpar arquivos temporários em caso de erro
        try:
            if 'temp_wav' in locals() and os.path.exists(temp_wav):
                os.remove(temp_wav)
            if 'final_audio' in locals() and os.path.exists(final_audio):
                os.remove(final_audio)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Forced alignment failed: {str(e)}")


@app.get("/models")
async def list_models():
    """List available models"""
    return {
        "models": {
            name: {
                "name": config["name"],
                "languages": config["supported_languages"],
                "loaded": name in models
            }
            for name, config in MODEL_CONFIG.items()
        },
        "voice_presets": VOICE_PRESETS
    }

# ============================================
# STARTUP/SHUTDOWN
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Starting MMS-TTS API with Sherpa-ONNX")
    logger.info(f"Available models: {list(MODEL_CONFIG.keys())}")
    
    # Initialize default users if configured
    if os.getenv("AUTO_INIT_DEFAULT_DATA", "true").lower() == "true":
        try:
            logger.info("Initializing default users and data...")
            results = db_manager.initialize_default_data()
            if results:
                logger.info(f"Default data initialized: {list(results.keys())}")
        except Exception as e:
            logger.warning(f"Failed to initialize default data: {e}")
    
    # Preload default model
    try:
        logger.info("Preloading Hebrew model...")
        load_sherpa_onnx_model("hebrew")
    except Exception as e:
        logger.warning(f"Failed to preload Hebrew model: {e}")
    
    # Initialize Whisper model for word alignment
    if WORD_ALIGNMENT_AVAILABLE:
        try:
            logger.info("Initializing MFA (Montreal Forced Aligner) for forced alignment...")
            init_mfa()
            logger.info("✅ Whisper model ready for forced alignment")
        except Exception as e:
            logger.warning(f"⚠️  Failed to initialize Whisper model: {e}")
            logger.warning("   Word alignment features will not be available")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    scheduler.shutdown()
    models.clear()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
