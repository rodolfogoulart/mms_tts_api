from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from transformers import VitsModel, AutoTokenizer
from accelerate import Accelerator
from scipy.io.wavfile import write
from pydub import AudioSegment
import torch
import numpy as np
import os
import uuid
import logging


# Importar o router de monitoring
from .monitoring import router as monitoring_router

app = FastAPI(title="Hebrew & Greek TTS API", description="API especializada em TTS para Hebraico e Grego usando MMS-TTS")

# Incluir as rotas de monitoring
app.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
# Alternativamente, sem prefix para manter as rotas no nível raiz:
# app.include_router(monitoring_router, tags=["monitoring"])

# Configuração de logging
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
    # "english": {
    #     "name": "MMS-TTS English",
    #     "model_id": "facebook/mms-tts-eng",
    #     "type": "mms",
    #     "supported_languages": {"eng": "English"}
    # },
    # "portuguese": {
    #     "name": "MMS-TTS Portuguese",
    #     "model_id": "facebook/mms-tts-por",
    #     "type": "mms",
    #     "supported_languages": {"por": "Portuguese"}
    # },
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

@app.get("/")
def root():
    return {
        "message": "Hebrew & Greek TTS API (Accelerated)",
        "models": {k: v["name"] for k, v in MODEL_CONFIG.items()},
        "supported_languages": ["heb (Hebrew)", "ell (Greek)"],
        "endpoints": ["/speak", "/models", "/languages", "/health", "/voice-presets"],
        "performance": {
            "accelerate_enabled": True,
            "mixed_precision": accelerator.mixed_precision,
            "device": str(device),
            "cuda_available": has_cuda,
            "torch_dtype": str(torch_dtype)
        }
    }

@app.post("/speak")
def speak(
    text: str = Form(...), 
    lang: str = Form(...), 
    model: str = Form(default="auto"),
    preset: str = Form(default=None, description="Preset de voz (natural, expressive, robotic, slow, fast)"),
    speed: float = Form(default=None, ge=0.1, le=3.0, description="Velocidade de fala (0.1-3.0) - Simplificado")
):
    """
    Gera áudio com presets ou configurações simplificadas (Accelerated)
    
    NOTA: MMS-TTS tem limitações nos parâmetros avançados.
    Apenas 'speed' é suportado através de pós-processamento.
    """
    try:
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
        
        # Gerar áudio usando MMS-TTS com accelerate (compatível CPU/GPU)
        inputs = tts_tokenizer(text, return_tensors="pt")
        
        with torch.no_grad():
            # Usar autocast apenas se mixed precision estiver habilitado
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
        
        # Converter para numpy (garantir que está na CPU e em float32)
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
        
        logger.info(f"Generated audio (accelerated): '{text}' ({lang}) - speed:{final_speed} - {config_source}")
        
        return FileResponse(
            mp3_path, 
            media_type="audio/mpeg", 
            filename=f"tts_{lang}_{temp_id}.mp3",
            headers={
                "X-Model-Used": model_config["name"],
                "X-Language": model_config["supported_languages"][lang],
                "X-Voice-Config": f"speed:{final_speed}",
                "X-Config-Source": config_source,
                "X-Preset-Used": preset if preset else "none",
                "X-Accelerate-Enabled": "true",
                "X-Mixed-Precision": accelerator.mixed_precision,
                "X-Device": str(device),
                "X-Torch-Dtype": str(torch_dtype)
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating audio (accelerated): {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {
        "status": "ok", 
        "message": "Hebrew & Greek TTS API is running (Accelerated)",
        "device": str(device),
        "loaded_models": list(models.keys()),
        "supported_languages": ["heb", "ell"],
        "performance": {
            "accelerate_enabled": True,
            "mixed_precision": accelerator.mixed_precision,
            "device_type": device.type if hasattr(device, 'type') else str(device),
            "cuda_available": has_cuda,
            "torch_dtype": str(torch_dtype)
        }
    }

@app.get("/models")
def get_models():
    """Lista todos os modelos disponíveis"""
    return {
        "models": MODEL_CONFIG,
        "total_models": len(MODEL_CONFIG),
        "performance_info": {
            "accelerate_enabled": True,
            "mixed_precision": accelerator.mixed_precision,
            "device": str(device),
            "cuda_available": has_cuda
        }
    }

@app.get("/languages")
def get_supported_languages():
    """Lista todos os idiomas suportados por todos os modelos"""
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
        "models_info": {k: v["name"] for k, v in MODEL_CONFIG.items()}
    }

@app.get("/voice-presets")
def get_voice_presets():
    """Lista presets de voz disponíveis (simplificados para MMS-TTS)"""
    return {
        "presets": VOICE_PRESETS,
        "note": "MMS-TTS models have limited parameter support. Only speed adjustment is available.",
        "available_parameters": ["speed"],
        "performance": {
            "accelerate_optimized": True,
            "mixed_precision": accelerator.mixed_precision,
            "device": str(device)
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
