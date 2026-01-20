"""
Word-level alignment module using faster-whisper
Otimizado para ARM64 CPU (Oracle VM.Standard.A1.Flex - 4 OCPUs, 24GB RAM)

Performance considerations:
- Modelo 'base' para melhor acurácia (vs 'tiny')
- int8 quantization para reduzir uso de memória
- Explicitamente CPU-only (sem GPU overhead)
- Thread-safe para concorrência (2-3 requests simultâneos)
- Preserva Unicode (niqqud hebraico, acentos gregos)
"""

import os
import logging
import unicodedata
import re
import threading
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Cache directory for faster-whisper models
WHISPER_CACHE_DIR = os.getenv("WHISPER_CACHE_DIR", "/app/.cache/whisper")

# Global model instance (inicializado no startup da aplicação)
_whisper_model = None
_model_lock = threading.Lock()  # Thread-safety para inicialização


def init_whisper_model():
    """
    Inicializa modelo faster-whisper no startup da aplicação.
    Deve ser chamado UMA VEZ durante a inicialização do FastAPI.
    
    Performance:
    - Modelo 'base': ~150MB, melhor acurácia que 'tiny'
    - int8 compute: reduz memória ~50% vs float16
    - num_workers=2: balanceado para 4 OCPUs ARM64
    - CPU-only: Oracle VM não tem GPU
    
    Thread-safety: Usa lock para evitar inicialização duplicada
    """
    global _whisper_model
    
    with _model_lock:
        if _whisper_model is not None:
            logger.warning("Whisper model already initialized, skipping")
            return _whisper_model
        
        try:
            from faster_whisper import WhisperModel
            
            logger.info("🔧 Initializing faster-whisper 'base' model (ARM64 CPU, int8)...")
            
            # Criar diretório de cache
            os.makedirs(WHISPER_CACHE_DIR, exist_ok=True)
            
            # Configuração otimizada para ARM64 CPU (Oracle VM)
            _whisper_model = WhisperModel(
                "base",                    # Melhor acurácia que 'tiny' (~150MB)
                device="cpu",              # CPU-only (sem GPU overhead)
                compute_type="int8",       # Quantização: menor memória, boa performance
                download_root=WHISPER_CACHE_DIR,
                num_workers=2,             # 2 workers para 4 OCPUs (balanceado)
                cpu_threads=4              # 4 threads por worker (total 8 threads)
            )
            
            logger.info("✅ faster-whisper 'base' model loaded successfully")
            logger.info(f"   - Device: CPU (ARM64)")
            logger.info(f"   - Compute: int8 quantization")
            logger.info(f"   - Workers: 2 (threads: 4 each)")
            
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


def normalize_for_matching(text: str) -> str:
    """
    Normaliza texto APENAS para matching fuzzy (não para exibição)
    Remove acentos/diacríticos mas preserva estrutura das palavras
    """
    # Decompor caracteres Unicode (separar base + diacríticos)
    decomposed = unicodedata.normalize('NFD', text)
    
    # Remover apenas marcas diacríticas (categoria Mn = Nonspacing Mark)
    # Mantém letras base intactas
    base_text = ''.join(
        char for char in decomposed 
        if unicodedata.category(char) != 'Mn'
    )
    
    # Recompor e converter para minúsculas
    return unicodedata.normalize('NFC', base_text).lower()


def fuzzy_match_words(
    transcribed_words: List[str], 
    original_text: str,
    threshold: float = 0.4  # ← REDUZIDO de 0.5 para 0.4
) -> Tuple[List[str], List[float], List[Tuple[int, int]]]:
    """
    Faz matching avançado entre palavras transcritas e texto original.
    Otimizado para hebraico/grego com algoritmo melhorado.
    
    Algoritmo:
    1. Separa palavras do texto original (preservando Unicode)
    2. Normaliza ambas as listas (remove diacríticos para comparação)
    3. Para cada palavra transcrita:
       a. Busca melhor match em janela deslizante (EXPANDIDA para 10 palavras)
       b. Calcula similaridade com SequenceMatcher (Ratcliff-Obershelp)
       c. Aceita match se ratio >= threshold OU é palavra sequencial
    4. Retorna palavras ORIGINAIS (com Unicode preservado)
    
    Performance:
    - Janela de 10 palavras: O(10n) ≈ O(n) ainda aceitável
    - SequenceMatcher é otimizado em C (rápido)
    - Pre-normalization cache evita recomputação
    
    Args:
        transcribed_words: Palavras do Whisper (podem ter erros)
        original_text: Texto original com diacríticos
        threshold: Similaridade mínima (0.0-1.0), padrão 0.4
    
    Returns:
        Tupla: (palavras matched, scores de confiança, posições no texto)
    """
    # Separar palavras do texto original (preservando Unicode) COM POSIÇÕES
    original_words = []
    word_positions = []
    
    for match in re.finditer(r'\S+', original_text):
        original_words.append(match.group())
        word_positions.append((match.start(), match.end()))
    
    if not original_words:
        logger.warning("Original text has no words")
        return [], [], []
    
    # Normalizar para matching (remove diacríticos)
    original_normalized = [normalize_for_matching(w) for w in original_words]
    transcribed_normalized = [normalize_for_matching(w) for w in transcribed_words]
    
    matched_words = []
    confidence_scores = []
    text_positions = []
    original_idx = 0
    
    # ← NOVO: Rastrear palavras já usadas para evitar duplicatas
    used_indices = set()
    
    for trans_idx, trans_word in enumerate(transcribed_normalized):
        best_match = None
        best_ratio = 0.0
        best_idx = original_idx
        
        # ← EXPANDIDO: Janela deslizante de 10 palavras (antes era 5)
        # Permite pular mais palavras se Whisper omitiu/adicionou
        search_start = max(0, original_idx - 2)  # ← NOVO: Olhar 2 palavras atrás também
        search_end = min(len(original_normalized), original_idx + 10)
        
        for i in range(search_start, search_end):
            # ← NOVO: Pular palavras já usadas (evita duplicatas)
            if i in used_indices:
                continue
                
            orig_word = original_normalized[i]
            
            # Calcular similaridade (Ratcliff-Obershelp algorithm)
            ratio = SequenceMatcher(None, trans_word, orig_word).ratio()
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = original_words[i]  # Palavra ORIGINAL (com Unicode)
                best_idx = i
        
        # ← AJUSTADO: Critério de aceitação mais rigoroso
        # 1. Similaridade >= threshold (agora 40%)
        # 2. OU é a próxima palavra sequencial (aceita mesmo com baixo score)
        # 3. OU é a única palavra restante
        # 4. E NÃO foi usada ainda
        accept_match = (
            best_ratio >= threshold and 
            best_idx not in used_indices
        ) or (
            best_idx == original_idx and 
            best_idx not in used_indices
        ) or (
            original_idx >= len(original_words) - 1 and 
            best_idx not in used_indices
        )
        
        if accept_match and best_match:
            matched_words.append(best_match)
            confidence_scores.append(best_ratio)
            text_positions.append(word_positions[best_idx])
            used_indices.add(best_idx)  # ← NOVO: Marcar como usado
            original_idx = best_idx + 1
        else:
            # ← AJUSTADO: Fallback mais inteligente
            # Se confidence muito baixa (< 0.3), provavelmente é ruído do Whisper
            # Não adicionar ao resultado final
            if best_ratio < 0.3:
                logger.debug(f"Skipping low-confidence word: '{trans_word}' (score: {best_ratio:.2f})")
                continue
            
            # Fallback: usar palavra transcrita se tiver alguma similaridade
            fallback_word = transcribed_words[trans_idx] if trans_idx < len(transcribed_words) else trans_word
            matched_words.append(fallback_word)
            confidence_scores.append(best_ratio)
            text_positions.append((-1, -1))  # Posição desconhecida
            logger.debug(f"Low confidence match: '{trans_word}' -> '{fallback_word}' (score: {best_ratio:.2f})")
    
    # Log estatísticas de matching
    if confidence_scores:
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        skipped = len(transcribed_words) - len(matched_words)
        logger.info(f"Matching complete: {len(matched_words)}/{len(transcribed_words)} words, "
                   f"avg confidence: {avg_confidence:.2f}, skipped: {skipped}")
    
    return matched_words, confidence_scores, text_positions


def align_words(audio_path: str, text: str, lang: str) -> List[Dict]:
    """
    Alinha palavras do áudio com timestamps usando faster-whisper.
    
    Otimizações para ARM64:
    - Modelo 'base' pré-carregado (melhor acurácia)
    - beam_size=3 (balanceado: qualidade vs velocidade)
    - vad_filter=True (remove silêncios, melhora acurácia)
    - language explícito (evita detecção automática)
    - temperature=0.0 (determinístico, sem variação)
    
    Graceful degradation:
    - NUNCA lança exceção (retorna [] em caso de erro)
    - Log detalhado para debugging
    - Fallback se matching falhar
    
    Performance esperada (ARM64, 4 OCPUs):
    - Áudio 3-5s: ~1.5-2.5s de processamento
    - Áudio 10s: ~3-5s de processamento
    - Concorrência: suporta 2-3 requests simultâneos
    
    Args:
        audio_path: Caminho do arquivo MP3/WAV
        text: Texto original (com niqqud/acentos preservados)
        lang: Código de idioma MMS ('heb', 'ell', 'por')
    
    Returns:
        Lista: [{"text": "palavra", "start": 0.0, "end": 0.5, "textStart": 0, "textEnd": 7, "confidence": 0.95}, ...]
        Lista vazia [] se falhar (graceful degradation)
    """
    try:
        # Validar arquivo de áudio
        if not os.path.exists(audio_path):
            logger.error(f"❌ Audio file not found: {audio_path}")
            return []
        
        # Obter modelo (deve estar pré-inicializado)
        try:
            model = get_whisper_model()
        except RuntimeError as e:
            logger.error(f"❌ {e}")
            return []
        
        # Mapear código de idioma MMS -> Whisper ISO
        from .multi_model_api import WHISPER_LANG_MAP
        whisper_lang = WHISPER_LANG_MAP.get(lang, lang)
        
        logger.info(f"🎯 Starting word alignment: {os.path.basename(audio_path)} (lang: {whisper_lang})")
        
        # Transcrever com word-level timestamps
        # Configuração otimizada para ARM64 CPU
        segments, info = model.transcribe(
            audio_path,
            language=whisper_lang,     # Explícito: evita detecção automática (mais rápido)
            word_timestamps=True,      # Ativar timestamps por palavra
            vad_filter=True,           # Voice Activity Detection: remove silêncios
            beam_size=3,               # Reduzido de 5: balanceado para CPU
            best_of=3,                 # Reduzido: menos candidates, mais rápido
            temperature=0.0,           # Determinístico (greedy decoding)
            condition_on_previous_text=False,  # Independente: melhor para frases curtas
            compression_ratio_threshold=2.4,   # Detecta repetições
            log_prob_threshold=-1.0,           # Filtro de baixa confiança
            no_speech_threshold=0.6            # Detecta silêncio
        )
        
        # Extrair palavras com timestamps
        transcribed_words = []
        word_segments = []
        
        for segment in segments:
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    word_text = word.word.strip()
                    if word_text:  # Ignorar vazios
                        transcribed_words.append(word_text)
                        word_segments.append({
                            'text': word_text,
                            'start': round(word.start, 2),
                            'end': round(word.end, 2),
                            'probability': getattr(word, 'probability', 1.0)
                        })
        
        if not word_segments:
            logger.warning(f"⚠️  No words detected in audio: {audio_path}")
            return []
        
        logger.info(f"📝 Transcribed {len(transcribed_words)} words from Whisper")
        
        # Fazer fuzzy matching com texto original (preservar Unicode)
        matched_words, confidence_scores, text_positions = fuzzy_match_words(
            transcribed_words, 
            text,
            threshold=0.5  # 50% similaridade mínima
        )
        
        # Combinar palavras matched com timestamps
        result = []
        for i, word_data in enumerate(word_segments):
            # Usar palavra original (com Unicode) se disponível
            if i < len(matched_words):
                word_text = matched_words[i]
                match_confidence = confidence_scores[i] if i < len(confidence_scores) else 0.0
                text_start, text_end = text_positions[i] if i < len(text_positions) else (-1, -1)
            else:
                # Fallback: palavra transcrita
                word_text = word_data['text']
                match_confidence = 0.0
                text_start, text_end = -1, -1
            
            result.append({
                'text': word_text,
                'start': word_data['start'],
                'end': word_data['end'],
                'textStart': text_start,
                'textEnd': text_end,
                'confidence': round(match_confidence, 2)  # Adicionar score de confiança
            })
        
        # Validação final
        if result:
            total_duration = result[-1]['end']
            avg_confidence = sum(w['confidence'] for w in result) / len(result)
            logger.info(f"✅ Alignment complete: {len(result)} words, "
                       f"duration: {total_duration:.2f}s, "
                       f"avg confidence: {avg_confidence:.2f}")
        return result
        
    except ImportError as e:
        logger.error(f"❌ faster-whisper not available: {e}")
        return []
    except Exception as e:
        # CRÍTICO: NUNCA lançar exceção (graceful degradation)
        logger.error(f"❌ Error during word alignment: {e}", exc_info=True)
        return []


def validate_alignment(words: List[Dict], audio_duration: float) -> bool:
    """
    Valida se o alinhamento é razoável
    
    Args:
        words: Lista de palavras com timestamps
        audio_duration: Duração do áudio em segundos
    
    Returns:
        True se alinhamento parece válido
    """
    if not words:
        return False
    
    # Verificar se timestamps estão dentro da duração
    last_word_end = words[-1]['end']
    if last_word_end > audio_duration * 1.2:  # Tolerância de 20%
        logger.warning(f"Last word timestamp ({last_word_end}s) exceeds audio duration ({audio_duration}s)")
        return False
    
    # Verificar se timestamps estão em ordem crescente
    for i in range(len(words) - 1):
        if words[i]['end'] > words[i + 1]['start']:
            logger.warning(f"Word timestamps not in order: {words[i]} -> {words[i+1]}")
            return False
    
    return True
