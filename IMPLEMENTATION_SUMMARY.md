# 🎯 Implementação de Forced Alignment - Sumário

## 📋 Resumo das Mudanças

Este documento resume todas as alterações implementadas para adicionar suporte a **forced alignment** (alinhamento palavra-por-palavra) no projeto MMS-TTS API.

---

## 🔧 Arquivos Modificados

### 1. **`app/word_alignment.py`** ⭐ PRINCIPAL

**Nova função: `forced_align_audio_to_text()`**

Implementa o algoritmo de forced alignment usando Whisper em modo determinístico:

```python
def forced_align_audio_to_text(
    audio_path: str,
    original_text: str,
    language: str = "he",
    normalize_audio: bool = True
) -> Tuple[List[Dict], float]:
```

**Características:**
- ✅ Usa `initial_prompt` com o texto original (força Whisper a seguir o texto)
- ✅ Configuração determinística: `temperature=0`, `beam_size=1`
- ✅ Word timestamps ativados: `word_timestamps=True`
- ✅ Sem VAD (Voice Activity Detection) para evitar cortes
- ✅ Pré-processamento de áudio (normalização, mono, 16kHz)
- ✅ Fallback inteligente para timestamps estimados

**Parâmetros:**
- `audio_path`: Caminho do arquivo de áudio (MP3/WAV)
- `original_text`: Texto original (FONTE DA VERDADE)
- `language`: Código Whisper ('he', 'el', 'pt')
- `normalize_audio`: Se True, pré-processa áudio

**Retorno:**
```python
(word_timestamps, audio_duration)
```

**Estrutura de `word_timestamps`:**
```json
[
  {
    "text": "בְּרֵאשִׁית",
    "start": 0.0,
    "end": 0.82,
    "textStart": 0,
    "textEnd": 9,
    "confidence": 1.0
  }
]
```

---

### 2. **`app/multi_model_api.py`** ⭐ PRINCIPAL

**Novo endpoint: `/speak_sync`**

```python
@app.post("/speak_sync")
async def speak_with_word_alignment(
    text: str = Form(...),
    model: str = Form("hebrew"),
    speed: float = Form(1.0),
    output_format: str = Form("mp3"),
    return_audio: bool = Form(True),
    user = Depends(get_rate_limited_user)
):
```

**Fluxo de processamento:**

1. **Geração de áudio** (Sherpa-ONNX/MMS-TTS)
   - Converte texto em áudio de alta qualidade
   - Salva WAV temporário para Whisper

2. **Forced alignment** (Whisper)
   - Executa `forced_align_audio_to_text()`
   - Obtém timestamps palavra-por-palavra

3. **Conversão de formato**
   - MP3 ou WAV conforme solicitado
   - Base64 ou arquivo em cache

4. **Resposta JSON completa**
   - Áudio (base64 ou URL)
   - Timestamps por palavra
   - Estatísticas de alinhamento
   - Tempos de processamento

**Exemplo de resposta:**
```json
{
  "text": "בְּרֵאשִׁית בָּרָא אֱלֹהִים",
  "model": "hebrew",
  "speed": 1.0,
  "audio_duration": 2.45,
  "audio_base64": "SUQzBAAAAAAAI1RTU0U...",
  "word_timestamps": [...],
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

**Modificações adicionais:**
- Import do módulo `word_alignment`
- Inicialização do Whisper no `startup_event()`
- Verificação de disponibilidade (`WORD_ALIGNMENT_AVAILABLE`)

---

## 📄 Arquivos Criados

### 3. **`FORCED_ALIGNMENT.md`** 📖

Documentação completa do recurso:

- 📖 Visão geral do forced alignment
- 🎯 Características e diferenças vs ASR
- 📡 Especificação completa do endpoint
- 🔧 Configuração de variáveis de ambiente
- 🧪 Exemplos de código (Python, JavaScript)
- 🎨 Casos de uso práticos
- ⚠️ Troubleshooting e dicas
- 📊 Performance esperada

**Seções principais:**
1. Modo determinístico
2. Alinhamento robusto
3. Otimização para CPU
4. Endpoint `/speak_sync`
5. Configuração (Oracle vs Local)
6. Casos de uso (highlight, legendas, análise)

---

### 4. **`test_forced_alignment.py`** 🧪

Script completo de testes:

**Casos de teste:**
1. **Hebraico**: Gênesis 1:1
2. **Grego**: João 1:1
3. **Português**: Salmo 23:1

**Funcionalidades:**
- ✅ Health check da API
- ✅ Teste de cada idioma
- ✅ Análise de qualidade (match_ratio)
- ✅ Identificação de palavras problemáticas
- ✅ Geração de arquivos:
  - MP3 (áudio)
  - JSON (timestamps completos)
  - SRT (legendas)

**Como usar:**
```bash
python test_forced_alignment.py
```

**Output:**
```
test_output/
├── hebrew_genesis.mp3
├── hebrew_genesis_timestamps.json
├── hebrew_genesis.srt
├── greek_john.mp3
├── greek_john_timestamps.json
├── greek_john.srt
├── portuguese_psalm.mp3
├── portuguese_psalm_timestamps.json
└── portuguese_psalm.srt
```

---

### 5. **`demo_forced_alignment.html`** 🎨

Demo interativo completo:

**Características:**
- 🎨 Interface moderna e responsiva
- 🎯 Highlight palavra-por-palavra em tempo real
- 🎵 Player de áudio integrado
- 📊 Estatísticas visuais de alinhamento
- 🖱️ Click em palavras para pular para o timestamp
- 🌍 Suporte RTL (hebraico) e LTR (grego/português)

**Como usar:**
1. Abrir no navegador
2. Inserir texto (hebraico, grego ou português)
3. Selecionar idioma
4. Ajustar velocidade
5. Clicar "Generate & Align"
6. Assistir o highlight sincronizado!

**Tecnologias:**
- HTML5 + CSS3
- Vanilla JavaScript (sem dependências)
- Fetch API
- Web Audio API

---

## 🔑 Conceitos-Chave

### Forced Alignment vs ASR

| Aspecto | ASR Tradicional | Forced Alignment |
|---------|-----------------|------------------|
| **Objetivo** | Reconhecer texto desconhecido | Obter timestamps de texto conhecido |
| **Entrada** | Apenas áudio | Áudio + texto original |
| **Saída** | Texto transcrito | Timestamps alinhados ao texto original |
| **Correções** | Sim (corrige erros) | Não (mantém texto original) |
| **Use case** | Transcrição | Sincronização, karaoke, análise |

### Modo Determinístico

Configurações que garantem resultados **reproduzíveis**:

```python
model.transcribe(
    audio_path,
    temperature=0.0,      # Zero aleatoriedade
    beam_size=1,          # Busca gulosa (sem exploração)
    initial_prompt=text,  # Força seguir o texto
    word_timestamps=True  # Timestamps por palavra
)
```

### Alinhamento Robusto

O algoritmo `fuzzy_match_words()` lida com variações do Whisper:

1. **Normalização multilíngue**
   - Remove niqqud hebraico
   - Remove acentos gregos/portugueses
   - Converte para lowercase

2. **Fuzzy matching**
   - Match exato: 1.0
   - Similaridade >= 0.55: aceito
   - Sequência: evita matches fora de ordem

3. **Fallback inteligente**
   - Se match_ratio < 50%: timestamps estimados
   - Distribuição proporcional ao comprimento
   - Confiança = 0.3 (baixa)

---

## 🚀 Fluxo de Execução

### 1. Requisição HTTP
```
POST /speak_sync
- text: "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
- model: "hebrew"
- speed: 1.0
```

### 2. Geração de Áudio (TTS)
```
Sherpa-ONNX + MMS-TTS
→ audio_samples (numpy array)
→ Salva WAV temporário
→ Duração: 2.45s
```

### 3. Forced Alignment (Whisper)
```
Whisper.transcribe()
- initial_prompt = texto original
- temperature = 0
- beam_size = 1
→ word_segments: [{'text': '...', 'start': ..., 'end': ...}]
```

### 4. Alinhamento (Fuzzy Matching)
```
fuzzy_match_words()
→ Normaliza tokens
→ Match sequencial
→ Confiança por palavra
→ Fallback se necessário
```

### 5. Resposta JSON
```json
{
  "audio_base64": "...",
  "word_timestamps": [...],
  "alignment_stats": {...}
}
```

---

## 📊 Performance Esperada

### Oracle Free Tier (ARM64 CPU)

| Componente | Tempo | % |
|------------|-------|---|
| TTS | 0.1-0.3s | 15% |
| Whisper | 1.0-2.0s | 75% |
| Matching | 0.05-0.1s | 5% |
| Outros | 0.05-0.1s | 5% |
| **Total** | **1.2-2.5s** | **100%** |

**RTF:** ~0.5-1.0x (para 2-3s de áudio)

### Notebook Local (NVIDIA GPU)

| Componente | Tempo | % |
|------------|-------|---|
| TTS | 0.1-0.2s | 20% |
| Whisper | 0.3-0.6s | 60% |
| Matching | 0.05-0.1s | 15% |
| Outros | 0.05s | 5% |
| **Total** | **0.5-0.95s** | **100%** |

**RTF:** ~0.2-0.4x (mais rápido que tempo real!)

---

## ⚙️ Configuração

### Variáveis de Ambiente

```bash
# VPS Oracle (ARM64 CPU)
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_CACHE_DIR=/app/.cache/whisper

# Notebook Local (NVIDIA GPU)
WHISPER_MODEL=medium
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
WHISPER_CACHE_DIR=/app/.cache/whisper
```

### Memória

- **CPU (small + int8):** ~500MB
- **GPU (medium + float16):** ~1.5GB VRAM

### Acurácia

- **small:** 85-95% (hebraico/grego)
- **medium:** 90-98% (hebraico/grego)

---

## 🎨 Casos de Uso

### 1. App de Bíblia - Highlight Sincronizado

```javascript
audio.addEventListener('timeupdate', () => {
  const currentTime = audio.currentTime;
  const currentWord = wordTimestamps.find(
    w => currentTime >= w.start && currentTime <= w.end
  );
  if (currentWord) {
    highlightVerse(currentWord.textStart, currentWord.textEnd);
  }
});
```

### 2. Análise de Pronúncia

```python
low_confidence_words = [
    w for w in word_timestamps 
    if w['confidence'] < 0.7
]
print(f"Palavras com incerteza: {len(low_confidence_words)}")
```

### 3. Geração de Legendas (SRT)

```python
def generate_srt(word_timestamps):
    for i, word in enumerate(word_timestamps, 1):
        start = format_timestamp(word['start'])
        end = format_timestamp(word['end'])
        print(f"{i}\n{start} --> {end}\n{word['text']}\n")
```

---

## ✅ Checklist de Implementação

- [x] Função `forced_align_audio_to_text()` em `word_alignment.py`
- [x] Endpoint `/speak_sync` em `multi_model_api.py`
- [x] Inicialização do Whisper no startup
- [x] Documentação completa (`FORCED_ALIGNMENT.md`)
- [x] Script de teste (`test_forced_alignment.py`)
- [x] Demo HTML interativo (`demo_forced_alignment.html`)
- [x] Atualização do README principal
- [x] Suporte a 3 idiomas (hebraico, grego, português)
- [x] Fallback para timestamps estimados
- [x] Estatísticas de qualidade de alinhamento
- [x] Configuração via variáveis de ambiente

---

## 📚 Próximos Passos (Opcional)

### Melhorias Futuras

1. **Cache de alinhamentos**
   - Armazenar timestamps em cache
   - Evitar realinhamento do mesmo texto

2. **Suporte a mais idiomas**
   - Adicionar árabe, latim, etc.
   - Mapa de códigos de idioma

3. **Fine-tuning do Whisper**
   - Treinar em corpus bíblico
   - Melhorar acurácia em nomes próprios

4. **Modo de alta precisão**
   - `beam_size > 1` opcional
   - `temperature > 0` com múltiplas tentativas

5. **Visualização melhorada**
   - Gráfico de forma de onda
   - Espectrograma com marcadores

---

## 🔗 Referências

- [faster-whisper Documentation](https://github.com/guillaumekln/faster-whisper)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)
- [MMS-TTS Models](https://github.com/willwade/mms-tts-multilingual-models-onnx)

---

## 📝 Notas Técnicas

### Por que `initial_prompt`?

O Whisper usa o `initial_prompt` como "dica" do que esperar no áudio. Ao passar o texto completo:
- ✅ Whisper tende a seguir o texto fornecido
- ✅ Reduz substituições incorretas
- ✅ Melhora timestamps (sabe onde procurar)
- ⚠️ Não é 100% garantido (Whisper ainda pode variar)

Por isso usamos **fuzzy matching** para reconciliar variações.

### Por que `temperature=0`?

- `temperature > 0`: Adiciona aleatoriedade (exploração)
- `temperature = 0`: Sempre escolhe o token mais provável
- **Resultado:** Saída determinística e reproduzível

### Por que `beam_size=1`?

- `beam_size > 1`: Explora múltiplos caminhos (mais lento)
- `beam_size = 1`: Busca gulosa (mais rápido)
- **Resultado:** Menor latência, suficiente com `initial_prompt`

---

## 🏆 Conclusão

A implementação de forced alignment adiciona um recurso poderoso ao MMS-TTS API:

✅ **Alinhamento palavra-por-palavra preciso**  
✅ **Texto original como fonte da verdade**  
✅ **Modo determinístico e reproduzível**  
✅ **Robusto com fallback inteligente**  
✅ **Otimizado para CPU (Oracle Free Tier)**  
✅ **Documentação completa e exemplos**  

Perfeito para apps de Bíblia, karaoke, aprendizado de idiomas e análise de fala! 🎉
