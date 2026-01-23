"""
Word-level alignment module using faster-whisper
Otimizado para ARM64 CPU (Oracle VM.Standard.A1.Flex - 4 OCPUs, 24GB RAM)
e CUDA GPU (Acer Nitro V15 - NVIDIA GPU)

Performance considerations:
- Configurável via variáveis de ambiente (WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE)
- Fallback automático para CPU caso CUDA não disponível
- VPS Oracle: modelo 'small', int8, CPU-only (~500MB, 85-95% acurácia)
- Notebook Local: modelo 'medium', float16, CUDA (~1.5GB VRAM, 90-98% acurácia)
- Thread-safe para concorrência (2-3 requests simultâneos)
- Pré-processamento de áudio para melhor transcrição
- Preserva Unicode (niqqud hebraico, acentos gregos)
"""

import os
import logging
import unicodedata
import re
import threading
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from pydub import AudioSegment
from pydub.effects import normalize as normalize_audio

logger = logging.getLogger(__name__)

# Cache directory for faster-whisper models
WHISPER_CACHE_DIR = os.getenv("WHISPER_CACHE_DIR", "/app/.cache/whisper")

# Configurações Whisper via variáveis de ambiente
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")           # small (VPS) ou medium (Local)
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")           # cpu (VPS) ou cuda (Local)
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # int8 (VPS) ou float16 (Local)

# Global model instance (inicializado no startup da aplicação)
_whisper_model = None
_model_lock = threading.Lock()  # Thread-safety para inicialização


def init_whisper_model():
    """
    Inicializa modelo faster-whisper no startup da aplicação.
    Deve ser chamado UMA VEZ durante a inicialização do FastAPI.
    
    Configurações via variáveis de ambiente:
    - WHISPER_MODEL: 'small' (VPS) ou 'medium' (Local) 
    - WHISPER_DEVICE: 'cpu' (VPS) ou 'cuda' (Local)
    - WHISPER_COMPUTE_TYPE: 'int8' (VPS) ou 'float16' (Local)
    
    Performance:
    VPS Oracle (ARM64 CPU):
    - Modelo 'small': ~500MB, ALTA acurácia para hebraico/grego (85-95%)
    - int8 compute: reduz memória ~50% vs float16 (~1GB total)
    - num_workers=2: balanceado para 4 OCPUs ARM64
    
    Notebook Local (NVIDIA GPU):
    - Modelo 'medium': ~1.5GB VRAM, MUITO ALTA acurácia (90-98%)
    - float16 compute: melhor performance em GPU
    - num_workers=4: aproveita GPU NVIDIA
    - Fallback automático para CPU caso CUDA não disponível
    
    Thread-safety: Usa lock para evitar inicialização duplicada
    """
    global _whisper_model
    
    with _model_lock:
        if _whisper_model is not None:
            logger.warning("Whisper model already initialized, skipping")
            return _whisper_model
        
        try:
            from faster_whisper import WhisperModel
            
            # Detectar disponibilidade de CUDA
            device = WHISPER_DEVICE
            compute_type = WHISPER_COMPUTE_TYPE
            
            if device == "cuda":
                try:
                    import torch
                    if not torch.cuda.is_available():
                        logger.warning("⚠️  CUDA requested but not available, falling back to CPU")
                        device = "cpu"
                        compute_type = "int8"  # CPU funciona melhor com int8
                    else:
                        cuda_device = torch.cuda.get_device_name(0)
                        logger.info(f"🎮 CUDA available: {cuda_device}")
                except ImportError:
                    logger.warning("⚠️  PyTorch not available, falling back to CPU")
                    device = "cpu"
                    compute_type = "int8"
            
            logger.info(f"🔧 Initializing faster-whisper '{WHISPER_MODEL}' model...")
            logger.info(f"   - Device: {device}")
            logger.info(f"   - Compute type: {compute_type}")
            logger.info("   ⏱️  First load may take 2-5 minutes (downloading model)...")
            
            # Criar diretório de cache
            os.makedirs(WHISPER_CACHE_DIR, exist_ok=True)
            
            # Determinar número de workers baseado no dispositivo
            num_workers = 4 if device == "cuda" else 2
            cpu_threads = 8 if device == "cuda" else 4
            
            # Configuração otimizada
            _whisper_model = WhisperModel(
                WHISPER_MODEL,                # 'small' (VPS) ou 'medium' (Local)
                device=device,                # 'cpu' ou 'cuda' (com fallback)
                compute_type=compute_type,    # 'int8' (CPU) ou 'float16' (GPU)
                download_root=WHISPER_CACHE_DIR,
                num_workers=num_workers,      # 2 (CPU) ou 4 (GPU)
                cpu_threads=cpu_threads       # 4 (CPU) ou 8 (GPU)
            )
            
            logger.info(f"✅ faster-whisper '{WHISPER_MODEL}' model loaded successfully")
            logger.info(f"   - Device: {device.upper()}")
            logger.info(f"   - Compute: {compute_type}")
            logger.info(f"   - Workers: {num_workers} (threads: {cpu_threads} each)")
            
            if WHISPER_MODEL == "small":
                logger.info(f"   - Expected accuracy: 85-95% for Hebrew/Greek")
            elif WHISPER_MODEL == "medium":
                logger.info(f"   - Expected accuracy: 90-98% for Hebrew/Greek")
            
            return _whisper_model
            
        except ImportError as e:
            logger.error(f"❌ faster-whisper not installed: {e}")
            raise ImportError(
                "faster-whisper is required for word alignment. "
                "Install with: pip install faster-whisper"
            )
        except Exception as e:
            logger.error(f"❌ Error loading faster-whisper model: {e}")
            raise


def get_whisper_model():
    """
    Retorna instância do modelo Whisper (deve estar pré-inicializado).
    Raise exception se modelo não foi inicializado no startup.
    """
    if _whisper_model is None:
        raise RuntimeError(
            "Whisper model not initialized. Call init_whisper_model() during app startup."
        )
    return _whisper_model


def preprocess_audio(audio_path: str) -> str:
    """
    Pré-processa áudio para melhorar acurácia da transcrição Whisper.
    
    Otimizações:
    1. Normaliza volume (evita áudio muito baixo/alto)
    2. Converte para mono (Whisper prefere mono)
    3. Resample para 16kHz (padrão Whisper)
    
    Args:
        audio_path: Caminho do arquivo MP3/WAV original
    
    Returns:
        Caminho do arquivo WAV normalizado (temp)
    """
    try:
        logger.debug(f"Preprocessing audio: {os.path.basename(audio_path)}")
        
        # Carregar áudio
        audio = AudioSegment.from_file(audio_path)
        
        # 1. Normalizar volume (boost para áudio baixo)
        audio = normalize_audio(audio)
        
        # 2. Converter para mono se estéreo
        if audio.channels > 1:
            audio = audio.set_channels(1)
            logger.debug("  - Converted to mono")
        
        # 3. Resample para 16kHz (padrão Whisper)
        if audio.frame_rate != 16000:
            audio = audio.set_frame_rate(16000)
            logger.debug(f"  - Resampled: {audio.frame_rate}Hz -> 16000Hz")
        
        # Salvar como WAV temporário
        temp_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        temp_path = os.path.join(temp_dir, f"{base_name}_normalized.wav")
        
        audio.export(temp_path, format='wav')
        logger.debug(f"  - Saved normalized: {os.path.basename(temp_path)}")
        
        return temp_path
        
    except Exception as e:
        logger.warning(f"Audio preprocessing failed: {e}, using original")
        return audio_path  # Fallback: usar original


def normalize_for_matching(text: str) -> str:
    """
    Normaliza texto APENAS para matching fuzzy (não para exibição)
    Remove acentos/diacríticos e caracteres especiais multilingues
    
    Suporte: Hebraico (Niqqud), Grego (Acentos), Português (Acentos)
    """
    if not text:
        return ""
    
    # Decompor caracteres Unicode (separar base + diacríticos)
    decomposed = unicodedata.normalize('NFD', text)
    
    # Lista extendida de caracteres a remover (Mantendo apenas letras base e números)
    # Remove:
    # - Mn: Nonspacing Mark (Acentos, Niqqud, Cantillation)
    # - Mc: Spacing Combining Mark
    # - Me: Enclosing Mark
    # - Po: Punctuation, Other (incluindo Maqaf hebraico, hifens)
    # - Pd: Punctuation, Dash
    
    base_text = ""
    for char in decomposed:
        cat = unicodedata.category(char)
        # Manter letras (L*), números (N*) e espaços (Z*)
        if cat.startswith('L') or cat.startswith('N') or cat.startswith('Z'):
            base_text += char
        # Casos especiais que QUEREMOS remover
        elif char == '\u05BE': # HEBREW PUNCTUATION MAQAF
            base_text += " "   # Substituir por espaço para separar palavras compostas? Não, melhor ignorar para matching aglutinado ou separar?
                               # O Whisper tende a separar. Vamos ignorar o caracter para aglutinar ou splitar?
                               # "Al-Penei" -> Whisper: "Al Penei" ou "Alpenei"? 
                               # Se removermos, "Al-Penei" vira "AlPenei". 
                               # Melhor substituir por espaço se for separador de palavras real, ou remover se for aglutinador.
                               # No hebraico Maqaf une palavras. Vamos remover para 'colar' ou substituir por espaço?
                               # Vamos remover pontuações.
            pass
        elif char in ('-', '–', '—', '_'): # Hifens diversos
            pass
    
    # Recompor e converter para minúsculas
    normalized = unicodedata.normalize('NFC', base_text).lower()
    
    # Remover qualquer caracter não-alfanumérico restante (segurança)
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    return normalized

def fuzzy_match_words(
    word_segments: list, 
    original_text: str,
    threshold: float = 0.55,
    audio_duration: float = 0.0
) -> list:
    """
    Novo algoritmo de alinhamento robusto (Anchor-Based)
    Garante que o output corresponda EXATAMENTE às palavras do texto original,
    preenchendo timestamps onde houver match confiável no Whisper.
    
    Se Whisper falhar completamente (menos de 50% das palavras matched),
    retorna timestamps estimados baseados no comprimento do texto.
    
    Args:
        word_segments: Lista de segmentos do Whisper [{'text':..., 'start':..., 'end':...}]
        original_text: Texto fonte completo
        threshold: Score mínimo para considerar um match (0.55 é bom para palavras curtas)
        audio_duration: Duração total do áudio em segundos (para estimativa)
        
    Returns:
        Lista de dicts alinhados 1:1 com as palavras do original_text
    """
    
    # 1. Tokenizar texto original mantendo posições reais
    # \S+ captura qualquer sequência que não seja espaço em branco (inclui pontuação grudada)
    original_tokens = []
    for match in re.finditer(r'\S+', original_text):
        token_text = match.group()
        original_tokens.append({
            'text': token_text,                 # Texto original exato
            'norm': normalize_for_matching(token_text), # Texto normalizado para busca
            'textStart': match.start(),
            'textEnd': match.end(),
            'start': -1.0,                     # Timestamp inicial (a preencher)
            'end': -1.0,                       # Timestamp final (a preencher)
            'confidence': 0.0,
            'matched': False
        })
    
    if not original_tokens:
        logger.warning("Original text has no tokens")
        return []
    
    # 2. Preparar tokens do Whisper
    trans_tokens = []
    for ws in word_segments:
        if not ws.get('text', '').strip(): continue
        trans_tokens.append({
            'text': ws['text'],
            'norm': normalize_for_matching(ws['text']),
            'start': ws['start'],
            'end': ws['end']
        })

    # 3. Alinhamento Sequencial (Greedy Anchor Matching)
    t_cursor = 0 # Cursor na lista de transcrição
    LOOKAHEAD_TRANS = 8
    
    for o_idx, o_token in enumerate(original_tokens):
        o_norm = o_token['norm']
        if not o_norm: continue
            
        best_score = 0.0
        best_t_idx = -1
        
        # Procurar match na janela do Whisper
        search_limit = min(len(trans_tokens), t_cursor + LOOKAHEAD_TRANS)
        
        for t in range(t_cursor, search_limit):
            t_data = trans_tokens[t]
            t_norm = t_data['norm']
            if not t_norm: continue
            
            # Match exato tem prioridade
            if o_norm == t_norm:
                best_score = 1.0
                best_t_idx = t
                break
            
            # Fuzzy match
            score = SequenceMatcher(None, o_norm, t_norm).ratio()
            dist = t - t_cursor
            final_score = score - (dist * 0.02)
            
            if final_score > best_score and score >= threshold:
                best_score = final_score
                best_t_idx = t
        
        # Aplicar match se encontrado
        if best_t_idx != -1:
            match_data = trans_tokens[best_t_idx]
            o_token['start'] = match_data['start']
            o_token['end'] = match_data['end']
            o_token['confidence'] = round(best_score if best_score <= 1.0 else 1.0, 2)
            o_token['matched'] = True
            t_cursor = best_t_idx + 1 
            
    # 4. Verificar qualidade do alinhamento
    matched_count = sum(1 for token in original_tokens if token['matched'])
    match_ratio = matched_count / len(original_tokens) if original_tokens else 0
    
    # Se menos de 50% das palavras foram matched E temos duração do áudio,
    # usar timestamps estimados baseados em distribuição uniforme
    if match_ratio < 0.5 and audio_duration > 0:
        logger.warning(f"⚠️  Low alignment quality ({match_ratio:.1%}), using estimated timestamps")
        
        # Calcular caracteres totais para distribuição proporcional
        total_chars = sum(len(token['text']) for token in original_tokens)
        
        current_time = 0.0
        for token in original_tokens:
            # Tempo proporcional ao comprimento da palavra
            word_duration = (len(token['text']) / total_chars) * audio_duration
            token['start'] = round(current_time, 2)
            token['end'] = round(current_time + word_duration, 2)
            token['confidence'] = 0.3  # Baixa confiança para estimativas
            token['matched'] = True  # Marcar como matched para incluir timestamps
            current_time += word_duration
    
    # 5. Construir resultado final
    result = []
    for token in original_tokens:
        # Só incluir timestamps se houve match (ou estimativa)
        start = token['start'] if token['matched'] else -1.0
        end = token['end'] if token['matched'] else -1.0
        
        result.append({
            'text': token['text'],
            'start': start,
            'end': end,
            'textStart': token['textStart'],
            'textEnd': token['textEnd'],
            'confidence': token['confidence']
        })
        
    matched_count = sum(1 for r in result if r['confidence'] > 0)
    logger.info(f"Alignment stats: {matched_count}/{len(result)} origin words matched.")
    
    return result


def align_words(audio_path: str, text: str, lang: str) -> list:
    """
    Alinha palavras do áudio com timestamps usando faster-whisper.
    """
    try:
        if not os.path.exists(audio_path):
            logger.error(f"❌ Audio file not found: {audio_path}")
            return []
        
        try:
            model = get_whisper_model()
        except RuntimeError as e:
            logger.error(f"❌ {e}")
            return []
        
        from .multi_model_api import WHISPER_LANG_MAP
        whisper_lang = WHISPER_LANG_MAP.get(lang, lang)
        
        logger.info(f"🎯 Starting word alignment (Anchor-Based): {os.path.basename(audio_path)}")
        
        preprocessed_path = preprocess_audio(audio_path)
        
        # Usar início do texto como prompt para guiar o Whisper
        prompt_text = text[:200].strip() if text else ("תנ״ך" if lang == "heb" else None)

        # Transcrever com word-level timestamps
        segments, info = model.transcribe(
            preprocessed_path,
            language=whisper_lang,
            word_timestamps=True,
            vad_filter=False,  # Desabilitar VAD - estava removendo todo o áudio
            beam_size=10,  # Aumentado para melhor precisão (era 5)
            best_of=5,
            patience=1.0, 
            temperature=0.0,
            condition_on_previous_text=False,
            initial_prompt=prompt_text
        )
        
        if preprocessed_path != audio_path and os.path.exists(preprocessed_path):
            try:
                os.remove(preprocessed_path)
            except Exception:
                pass
        
        # Extrair palavras com timestamps (Flat list)
        word_segments = []
        for segment in segments:
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    word_text = word.word.strip()
                    if word_text:
                        word_segments.append({
                            'text': word_text,
                            'start': round(word.start, 2),
                            'end': round(word.end, 2),
                            'probability': getattr(word, 'probability', 1.0)
                        })
        
        # Obter duração do áudio
        audio_duration = 0.0
        try:
            audio = AudioSegment.from_file(audio_path)
            audio_duration = len(audio) / 1000.0  # Converter de ms para segundos
        except Exception as e:
            logger.warning(f"Could not get audio duration: {e}")
        
        if not word_segments:
            logger.warning(f"⚠️  No words detected in audio")
            # Mesmo sem Whisper, tentar gerar timestamps estimados
            if audio_duration > 0:
                logger.info("Generating estimated timestamps without Whisper")
                return fuzzy_match_words([], text, threshold=0.55, audio_duration=audio_duration)
            return []
            
        logger.info(f"📝 Whisper detected {len(word_segments)} words")
        logger.info(f"   Whisper words: {[w['text'] for w in word_segments]}")
        
        # NOVO ALINHAMENTO (Original-Centric)
        # Passa a lista bruta do Whisper e o texto original + duração para fallback
        result = fuzzy_match_words(
            word_segments, 
            text,
            threshold=0.55,
            audio_duration=audio_duration

