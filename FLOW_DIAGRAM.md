# 🔄 Fluxo de Processamento - Forced Alignment

## Diagrama Visual do Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENTE (App de Bíblia)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ POST /speak_sync
                             │ {
                             │   text: "בְּרֵאשִׁית בָּרָא...",
                             │   model: "hebrew",
                             │   speed: 1.0
                             │ }
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API ENDPOINT                             │
│                    /speak_sync (FastAPI)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                 ┌───────────┴───────────┐
                 │                       │
                 ▼                       ▼
┌────────────────────────┐   ┌────────────────────────┐
│   1. GERAÇÃO ÁUDIO     │   │   2. FORCED ALIGNMENT  │
│   (Sherpa-ONNX)        │   │   (faster-whisper)     │
│                        │   │                        │
│  • Carregar modelo     │   │  • Modelo pré-carregado│
│  • Gerar audio_samples │   │  • temperature = 0     │
│  • Converter para WAV  │   │  • beam_size = 1       │
│  • Salvar temp file    │   │  • initial_prompt=texto│
│                        │   │  • word_timestamps=True│
│  Tempo: 0.1-0.3s       │   │  Tempo: 1.0-2.0s       │
└────────┬───────────────┘   └───────────┬────────────┘
         │                               │
         │ audio.wav                     │ word_segments[]
         │ (temp file)                   │ [{'text': '...', 
         │                               │   'start': 0.0,
         │                               │   'end': 0.5}]
         │                               │
         └───────────────┬───────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │  3. FUZZY MATCHING            │
         │  (fuzzy_match_words)          │
         │                               │
         │  • Tokenizar texto original   │
         │  • Normalizar (remove niqqud) │
         │  • Match sequencial           │
         │  • Calcular confiança         │
         │  • Fallback se < 50% match    │
         │                               │
         │  Tempo: 0.05-0.1s             │
         └───────────────┬───────────────┘
                         │
                         │ aligned_words[]
                         │ [{'text': 'בְּרֵאשִׁית',
                         │   'start': 0.0,
                         │   'end': 0.82,
                         │   'confidence': 1.0}]
                         │
                         ▼
         ┌───────────────────────────────┐
         │  4. CONVERSÃO FORMATO         │
         │  (MP3 ou WAV)                 │
         │                               │
         │  • AudioSegment.export()      │
         │  • Base64 encode              │
         │  • Ou salvar em cache         │
         │                               │
         │  Tempo: 0.05-0.1s             │
         └───────────────┬───────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │  5. RESPOSTA JSON             │
         │                               │
         │  {                            │
         │    "audio_base64": "...",     │
         │    "word_timestamps": [...],  │
         │    "alignment_stats": {...}   │
         │  }                            │
         └───────────────┬───────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENTE (App de Bíblia)                    │
│                                                                 │
│  • Recebe JSON com áudio + timestamps                          │
│  • Decodifica base64 → Blob de áudio                           │
│  • Cria elemento <audio>                                        │
│  • Adiciona listener 'timeupdate'                              │
│  • Highlight palavra-por-palavra sincronizado!                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Fluxo de Dados Detalhado

### 1. Entrada
```
Texto: "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
Modelo: hebrew
Velocidade: 1.0
```

### 2. Sherpa-ONNX (TTS)
```
Input: texto (string)
↓
Phoneme conversion
↓
VITS model inference
↓
Output: audio_samples (float32[])
        sample_rate: 22050 Hz
↓
Save: temp/uuid.wav
```

### 3. Whisper (Transcription)
```
Input: temp/uuid.wav + initial_prompt
↓
Audio preprocessing (16kHz, mono)
↓
Encoder (audio → features)
↓
Decoder (features → tokens + timestamps)
  - Guided by initial_prompt
  - temperature = 0 (deterministic)
  - beam_size = 1 (greedy)
↓
Output: segments[] with word_timestamps
[
  Word(text="בראשית", start=0.0, end=0.82),
  Word(text="ברא", start=0.82, end=1.24),
  Word(text="אלהים", start=1.24, end=2.45)
]
```

### 4. Fuzzy Matching
```
Input: 
  - word_segments (Whisper output)
  - original_text (fonte da verdade)
↓
Normalize both:
  "בְּרֵאשִׁית" → "בראשית"
  (remove niqqud, lowercase)
↓
Sequential matching:
  for each original_token:
    find best match in whisper tokens
    within lookahead window (8 tokens)
    using SequenceMatcher ratio
↓
Assign timestamps:
  original_token['start'] = matched['start']
  original_token['end'] = matched['end']
  original_token['confidence'] = ratio
↓
Fallback (if match_ratio < 50%):
  Estimate timestamps proportionally
  based on text length
↓
Output: aligned_words[]
[
  {
    text: "בְּרֵאשִׁית",  ← original (com niqqud)
    start: 0.0,
    end: 0.82,
    textStart: 0,
    textEnd: 9,
    confidence: 1.0
  }
]
```

### 5. Response
```json
{
  "text": "בְּרֵאשִׁית בָּרָא אֱלֹהִים",
  "model": "hebrew",
  "speed": 1.0,
  "audio_duration": 2.45,
  "audio_base64": "SUQzBAAAAAAAI1RTU0U...",
  "word_timestamps": [
    {
      "text": "בְּרֵאשִׁית",
      "start": 0.0,
      "end": 0.82,
      "textStart": 0,
      "textEnd": 9,
      "confidence": 1.0
    },
    {
      "text": "בָּרָא",
      "start": 0.82,
      "end": 1.24,
      "textStart": 10,
      "textEnd": 14,
      "confidence": 0.98
    },
    {
      "text": "אֱלֹהִים",
      "start": 1.24,
      "end": 2.45,
      "textStart": 15,
      "textEnd": 21,
      "confidence": 1.0
    }
  ],
  "alignment_stats": {
    "total_words": 3,
    "matched_words": 3,
    "match_ratio": 1.0
  },
  "processing_time": {
    "tts_seconds": 0.15,
    "alignment_seconds": 1.23,
    "total_seconds": 1.38
  }
}
```

---

## Arquitetura de Componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
└─────────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│   /speak       │  │  /speak_sync   │  │   /health      │
│   (TTS only)   │  │  (TTS+Align)   │  │                │
└────────────────┘  └────────┬───────┘  └────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ Sherpa-ONNX    │  │ faster-whisper │  │ fuzzy_match    │
│ (MMS-TTS)      │  │ (Whisper)      │  │ (alignment)    │
│                │  │                │  │                │
│ • Hebrew model │  │ • small model  │  │ • normalize()  │
│ • Greek model  │  │ • CPU/CUDA     │  │ • match()      │
│ • Port. model  │  │ • int8/float16 │  │ • fallback()   │
└────────────────┘  └────────────────┘  └────────────────┘
```

---

## Estado e Cache

### Modelos em Memória (Startup)

```
App Startup
↓
1. Init Sherpa-ONNX (Hebrew)
   ├─ Download if needed
   ├─ Load ONNX model (~10-15MB)
   └─ Cache in memory
↓
2. Init faster-whisper (small)
   ├─ Download if needed (~500MB)
   ├─ Load model weights
   ├─ Setup CPU/CUDA
   └─ Cache in memory
↓
Ready to serve requests!
```

### Cache de Áudio (Runtime)

```
Request text + model + speed
↓
Generate cache_key = hash(text+model+speed)
↓
Check if cache_key exists?
├─ YES → Return cached file
└─ NO  → Generate new audio
         ├─ TTS
         ├─ Alignment (if /speak_sync)
         ├─ Save to cache/
         └─ Return file
```

---

## Performance Breakdown

### Tempo Real (RTF = Real-Time Factor)

```
Exemplo: 2.5s de áudio

VPS Oracle (CPU):
├─ TTS: 0.15s      (RTF: 0.06x) ✅ MUITO RÁPIDO
├─ Whisper: 1.23s  (RTF: 0.49x) ✅ TEMPO REAL
├─ Match: 0.08s    (RTF: 0.03x) ✅ INSTANTÂNEO
└─ Total: 1.46s    (RTF: 0.58x) ✅ TEMPO REAL

Notebook (GPU):
├─ TTS: 0.12s      (RTF: 0.05x) ✅ MUITO RÁPIDO
├─ Whisper: 0.45s  (RTF: 0.18x) ✅ 5x MAIS RÁPIDO
├─ Match: 0.06s    (RTF: 0.02x) ✅ INSTANTÂNEO
└─ Total: 0.63s    (RTF: 0.25x) ✅ 4x TEMPO REAL
```

### Memória

```
VPS Oracle (CPU):
├─ Base (Python + FastAPI): ~100MB
├─ Sherpa-ONNX (Hebrew): ~50MB
├─ faster-whisper (small+int8): ~500MB
└─ Total: ~650MB ✅ Oracle Free Tier OK (24GB)

Notebook (GPU):
├─ System RAM: ~200MB
├─ VRAM (medium+float16): ~1.5GB
└─ Total GPU: ~1.5GB ✅ Entry GPU OK (4GB)
```

---

## Exemplo de Uso (Highlight)

### JavaScript Client

```javascript
// 1. Requisição
const response = await fetch('/speak_sync', {
  method: 'POST',
  body: new URLSearchParams({
    text: 'בְּרֵאשִׁית בָּרָא אֱלֹהִים',
    model: 'hebrew',
    return_audio: 'true'
  })
});

const result = await response.json();

// 2. Setup áudio
const audioBlob = base64ToBlob(result.audio_base64);
const audioUrl = URL.createObjectURL(audioBlob);
const audio = new Audio(audioUrl);

// 3. Highlight sincronizado
audio.addEventListener('timeupdate', () => {
  const t = audio.currentTime;
  
  // Encontrar palavra atual
  const currentWord = result.word_timestamps.find(
    w => t >= w.start && t <= w.end
  );
  
  if (currentWord) {
    // Remover highlight anterior
    document.querySelectorAll('.highlight').forEach(el => {
      el.classList.remove('highlight');
    });
    
    // Adicionar highlight atual
    const wordElement = document.querySelector(
      `[data-text-start="${currentWord.textStart}"]`
    );
    wordElement.classList.add('highlight');
  }
});

// 4. Play!
audio.play();
```

---

## Conclusão

Este diagrama mostra como o sistema integra:

1. ✅ **TTS de alta qualidade** (Sherpa-ONNX/MMS-TTS)
2. ✅ **Forced alignment preciso** (Whisper + fuzzy matching)
3. ✅ **API simples** (um endpoint, resposta completa)
4. ✅ **Performance otimizada** (CPU-friendly, < 2s)
5. ✅ **Uso prático** (highlight palavra-por-palavra)

**Perfeito para apps de Bíblia e aprendizado de idiomas!** 🎉
