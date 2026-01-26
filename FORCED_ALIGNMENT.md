# Forced Alignment - Guia de Uso

## 📖 Visão Geral

O endpoint `/speak_sync` implementa **forced alignment** palavra-por-palavra, combinando:

1. **MMS-TTS (Sherpa-ONNX)**: Geração de áudio de alta qualidade
2. **Whisper**: Alinhamento temporal (não reconhecimento)

O texto fornecido é a **ÚNICA FONTE DA VERDADE**. O Whisper é usado apenas para obter timestamps precisos, não para reconhecer ou corrigir o texto.

---

## 🎯 Características

### ✅ Modo Determinístico
- `temperature = 0` (sem aleatoriedade)
- `beam_size = 1` (busca determinística)
- `initial_prompt = texto original` (força Whisper a seguir o texto)

### ✅ Alinhamento Robusto
- Normalização multilíngue (hebraico, grego, português)
- Fuzzy matching para reconciliar pequenas variações
- Fallback para timestamps estimados se alinhamento falhar

### ✅ Otimizado para CPU
- Configuração via variáveis de ambiente
- Modelo Whisper 'small' para Oracle Free Tier
- int8 compute type para economia de memória

---

## 📡 Endpoint: POST `/speak_sync`

### Parâmetros

| Parâmetro | Tipo | Obrigatório | Padrão | Descrição |
|-----------|------|-------------|--------|-----------|
| `text` | string | ✅ Sim | - | Texto original (hebraico, grego ou português) |
| `model` | string | ❌ Não | `hebrew` | Modelo TTS: `hebrew`, `greek`, `portuguese` |
| `speed` | float | ❌ Não | `1.0` | Velocidade da fala (0.5 a 2.0) |
| `output_format` | string | ❌ Não | `mp3` | Formato do áudio: `mp3` ou `wav` |
| `return_audio` | bool | ❌ Não | `true` | Se `true`, retorna áudio em base64; se `false`, salva em cache |

### Exemplo de Requisição

```bash
curl -X POST "http://localhost:8000/speak_sync" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "text=בְּרֵאשִׁית בָּרָא אֱלֹהִים" \
  -d "model=hebrew" \
  -d "speed=1.0" \
  -d "output_format=mp3" \
  -d "return_audio=true"
```

### Resposta JSON

```json
{
  "text": "בְּרֵאשִׁית בָּרָא אֱלֹהִים",
  "model": "hebrew",
  "speed": 1.0,
  "audio_duration": 2.45,
  "audio_format": "mp3",
  "audio_base64": "SUQzBAAAAAAAI1RTU0UAAAA...",
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

## 🔧 Configuração

### Variáveis de Ambiente

Configure o comportamento do Whisper:

```bash
# Modelo Whisper (small para VPS, medium para local)
WHISPER_MODEL=small

# Dispositivo (cpu para VPS, cuda para GPU)
WHISPER_DEVICE=cpu

# Tipo de computação (int8 para CPU, float16 para GPU)
WHISPER_COMPUTE_TYPE=int8

# Diretório de cache dos modelos
WHISPER_CACHE_DIR=/app/.cache/whisper
```

### Configurações Recomendadas

#### Oracle Free Tier (ARM64 CPU)
```bash
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

**Performance esperada:**
- Memória: ~500MB
- Acurácia: 85-95% (hebraico/grego)
- RTF: ~1.0-1.5x (tempo real)

#### Notebook Local (NVIDIA GPU)
```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

**Performance esperada:**
- VRAM: ~1.5GB
- Acurácia: 90-98%
- RTF: ~0.3-0.5x (mais rápido que tempo real)

---

## 🧪 Testes

### Python
```python
import requests
import json
import base64

url = "http://localhost:8000/speak_sync"
data = {
    "text": "בְּרֵאשִׁית בָּרָא אֱלֹהִים",
    "model": "hebrew",
    "speed": 1.0,
    "output_format": "mp3",
    "return_audio": True
}

response = requests.post(url, data=data)
result = response.json()

print(f"Duration: {result['audio_duration']}s")
print(f"Words: {result['alignment_stats']['total_words']}")
print(f"Match ratio: {result['alignment_stats']['match_ratio']:.1%}")

# Salvar áudio
if 'audio_base64' in result:
    audio_bytes = base64.b64decode(result['audio_base64'])
    with open('output.mp3', 'wb') as f:
        f.write(audio_bytes)
    print("Audio saved to output.mp3")

# Imprimir timestamps
for word in result['word_timestamps']:
    print(f"{word['text']}: {word['start']:.2f}s - {word['end']:.2f}s")
```

### JavaScript (Fetch)
```javascript
const formData = new URLSearchParams();
formData.append('text', 'בְּרֵאשִׁית בָּרָא אֱלֹהִים');
formData.append('model', 'hebrew');
formData.append('speed', '1.0');
formData.append('output_format', 'mp3');
formData.append('return_audio', 'true');

fetch('http://localhost:8000/speak_sync', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
  },
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log(`Duration: ${data.audio_duration}s`);
  console.log(`Words: ${data.alignment_stats.total_words}`);
  console.log(`Match ratio: ${data.alignment_stats.match_ratio}`);
  
  // Criar elemento de áudio
  const audioSrc = `data:audio/mp3;base64,${data.audio_base64}`;
  const audio = new Audio(audioSrc);
  
  // Highlight palavra-por-palavra
  data.word_timestamps.forEach(word => {
    setTimeout(() => {
      console.log(`Highlighting: ${word.text}`);
      // Seu código de highlight aqui
    }, word.start * 1000);
  });
  
  audio.play();
});
```

---

## 📊 Estrutura do Output

### `word_timestamps[]`

Cada elemento contém:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `text` | string | Palavra original exata (com pontuação e diacríticos) |
| `start` | float | Timestamp de início (segundos) |
| `end` | float | Timestamp de fim (segundos) |
| `textStart` | int | Índice do primeiro caractere no texto original |
| `textEnd` | int | Índice após o último caractere |
| `confidence` | float | Confiança do alinhamento (0.0 a 1.0) |

**Observações:**
- `confidence = 1.0`: Match exato
- `confidence >= 0.55`: Match fuzzy confiável
- `confidence = 0.3`: Timestamp estimado (fallback)
- `confidence = 0.0`: Sem timestamp (palavra não matched)

### `alignment_stats`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total_words` | int | Total de palavras no texto original |
| `matched_words` | int | Palavras com timestamps confiáveis |
| `match_ratio` | float | Percentual de palavras matched (0.0 a 1.0) |

---

## 🎨 Casos de Uso

### 1. Highlight Palavra-por-Palavra em App de Bíblia
```javascript
// Sincronizar highlight com áudio
audio.addEventListener('timeupdate', () => {
  const currentTime = audio.currentTime;
  const currentWord = wordTimestamps.find(
    w => currentTime >= w.start && currentTime <= w.end
  );
  
  if (currentWord) {
    highlightWord(currentWord.textStart, currentWord.textEnd);
  }
});
```

### 2. Análise de Pronúncia
```python
# Identificar palavras com baixa confiança
low_confidence_words = [
    w for w in word_timestamps 
    if w['confidence'] < 0.7
]

print(f"Words with timing uncertainty: {len(low_confidence_words)}")
for word in low_confidence_words:
    print(f"  - {word['text']} (confidence: {word['confidence']:.2f})")
```

### 3. Geração de Legendas (SRT)
```python
def generate_srt(word_timestamps):
    srt_content = []
    for i, word in enumerate(word_timestamps, 1):
        start = format_timestamp(word['start'])
        end = format_timestamp(word['end'])
        srt_content.append(f"{i}\n{start} --> {end}\n{word['text']}\n")
    return "\n".join(srt_content)

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
```

---

## ⚠️ Troubleshooting

### Erro: "Word alignment feature not available"
**Causa:** `faster-whisper` não instalado

**Solução:**
```bash
pip install faster-whisper
```

### Baixa qualidade de alinhamento (match_ratio < 0.5)
**Causas possíveis:**
- Áudio com ruído ou baixa qualidade
- Velocidade muito rápida (`speed > 1.5`)
- Idioma incorreto

**Soluções:**
1. Reduzir velocidade: `speed=1.0`
2. Verificar modelo correto: `model=hebrew/greek/portuguese`
3. Usar modelo Whisper maior: `WHISPER_MODEL=medium`

### Timestamps imprecisos
**Causa:** Fallback para estimativa (match_ratio < 0.5)

**Identificação:**
```python
if result['alignment_stats']['match_ratio'] < 0.5:
    print("⚠️  Using estimated timestamps (low alignment quality)")
```

**Solução:**
- Melhorar qualidade do áudio de entrada
- Usar `normalize_audio=True` (padrão)

---

## 🚀 Performance

### Tempos Esperados (Oracle Free Tier)

| Componente | Tempo | % Total |
|------------|-------|---------|
| TTS (Sherpa-ONNX) | 0.1-0.3s | 10-20% |
| Whisper Transcription | 1.0-2.0s | 70-80% |
| Fuzzy Matching | 0.05-0.1s | 5-10% |
| **Total** | **1.2-2.5s** | **100%** |

**RTF (Real-Time Factor):** ~0.5-1.0x (para 2-3s de áudio)

---

## 📝 Notas Técnicas

### Diferenças vs ASR Tradicional
| Aspecto | ASR Tradicional | Forced Alignment |
|---------|-----------------|------------------|
| Objetivo | Reconhecer texto | Obter timestamps |
| Texto de entrada | ❌ Não usa | ✅ Fonte da verdade |
| Correção de texto | ✅ Sim | ❌ Não (mantém original) |
| `initial_prompt` | Contexto opcional | **Texto completo** |
| Output | Texto transcrito | Timestamps + texto original |

### Normalização Multilíngue
O fuzzy matching remove:
- **Hebraico:** Niqqud (נִקּוּד), Cantillation marks
- **Grego:** Acentos (ά, έ, ό), espíritos (ἀ, ἁ)
- **Português:** Acentos (á, ê, ç)

Isso permite matching robusto mesmo com pequenas variações do Whisper.

---

## 📚 Referências

- [faster-whisper](https://github.com/guillaumekln/faster-whisper)
- [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)
- [OpenAI Whisper](https://github.com/openai/whisper)

---

## 📄 Licença

Este projeto usa:
- MMS-TTS (Meta): CC-BY-NC 4.0
- Whisper (OpenAI): MIT License
