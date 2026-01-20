# 🎯 Word-Level Alignment API - Guia de Uso

## 📌 Visão Geral

O endpoint `/speak_sync` gera áudio TTS com **timestamps palavra-por-palavra**, permitindo sincronização precisa (karaoke-style highlighting).

**Diferenças entre endpoints:**
- `/speak` → Retorna apenas MP3 (rápido, leve)
- `/speak_sync` → Retorna JSON com MP3 + timestamps (mais pesado, mas com sincronização)

---

## 🔧 Endpoint: `POST /speak_sync`

### Parâmetros (Form Data)

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `text` | string | ✅ | Texto para converter (máx 5000 chars) |
| `lang` | string | ✅ | Código do idioma: `heb`, `ell`, `por` |
| `model` | string | ❌ | Modelo específico ou `auto` (padrão) |
| `preset` | string | ❌ | Preset de voz: `natural`, `slow`, `fast`, etc. |
| `speed` | float | ❌ | Velocidade customizada (0.1-3.0) |

### Headers de Autenticação

**Opção 1: JWT Bearer Token**
```http
Authorization: Bearer YOUR_JWT_TOKEN
```

**Opção 2: API Key**
```http
X-API-Key: YOUR_API_KEY
```

---

## 📤 Resposta

### JSON Response (Success - 200)

```json
{
  "audio_url": "/audio/tts_abc123def456.mp3",
  "language": "heb",
  "language_name": "Hebrew",
  "model_used": "MMS-TTS Hebrew",
  "words": [
    {
      "text": "בְּרֵאשִׁית",
      "start": 0.12,
      "end": 0.55
    },
    {
      "text": "בָּרָא",
      "start": 0.60,
      "end": 0.92
    },
    {
      "text": "אֱלֹהִים",
      "start": 0.98,
      "end": 1.34
    }
  ],
  "word_count": 3,
  "alignment_available": true,
  "cache_hit": false,
  "alignment_cache_hit": false
}
```

### Campos da Resposta

- **`audio_url`**: URL relativa para baixar o MP3 (requer autenticação)
- **`language`**: Código do idioma processado
- **`language_name`**: Nome do idioma em inglês
- **`model_used`**: Nome do modelo TTS utilizado
- **`words`**: Array de objetos com timestamps
  - `text`: Palavra original (com niqqud/acentos preservados)
  - `start`: Timestamp inicial em segundos
  - `end`: Timestamp final em segundos
- **`word_count`**: Número de palavras alinhadas
- **`alignment_available`**: `true` se alinhamento foi bem-sucedido
- **`cache_hit`**: `true` se áudio estava em cache
- **`alignment_cache_hit`**: `true` se alinhamento estava em cache

### Graceful Degradation

Se o alinhamento falhar (modelo não disponível, erro de processamento):
```json
{
  "audio_url": "/audio/tts_abc123def456.mp3",
  "language": "heb",
  "words": [],
  "word_count": 0,
  "alignment_available": false
}
```
⚠️ **O áudio sempre é retornado**, mesmo se o alinhamento falhar!

---

## 🧪 Exemplos de Uso

### 1. cURL - Hebraico com JWT

```bash
curl -X POST "https://your-api.com/speak_sync" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -F "text=בְּרֵאשִׁית בָּרָא אֱלֹהִים" \
  -F "lang=heb" \
  -F "speed=1.0"
```

### 2. Python - Grego com API Key

```python
import requests

url = "https://your-api.com/speak_sync"
headers = {"X-API-Key": "tts_your_api_key_here"}

data = {
    "text": "Ἐν ἀρχῇ ἦν ὁ λόγος",
    "lang": "ell",
    "preset": "slow"
}

response = requests.post(url, headers=headers, data=data)
result = response.json()

print(f"Audio: {result['audio_url']}")
print(f"Words: {len(result['words'])}")

for word in result['words']:
    print(f"  {word['text']}: {word['start']}s - {word['end']}s")
```

### 3. JavaScript/Fetch - Português

```javascript
const formData = new FormData();
formData.append('text', 'No princípio era o Verbo');
formData.append('lang', 'por');
formData.append('speed', '1.0');

fetch('https://your-api.com/speak_sync', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_JWT_TOKEN'
  },
  body: formData
})
.then(res => res.json())
.then(data => {
  console.log('Audio URL:', data.audio_url);
  console.log('Words with timestamps:', data.words);
  
  // Usar para karaoke/highlighting
  data.words.forEach(word => {
    console.log(`${word.text}: ${word.start}s - ${word.end}s`);
  });
});
```

---

## 🎬 Uso em Frontend - Karaoke Highlighting

### HTML + JavaScript Example

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    .word { padding: 2px 5px; margin: 2px; }
    .word.active { background-color: yellow; font-weight: bold; }
  </style>
</head>
<body>
  <div id="text-container"></div>
  <audio id="audio-player" controls></audio>

  <script>
    async function loadAndPlaySync() {
      // 1. Requisitar TTS com alinhamento
      const formData = new FormData();
      formData.append('text', 'בְּרֵאשִׁית בָּרָא אֱלֹהִים');
      formData.append('lang', 'heb');
      
      const response = await fetch('/speak_sync', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer YOUR_TOKEN' },
        body: formData
      });
      
      const data = await response.json();
      
      // 2. Configurar áudio
      const audio = document.getElementById('audio-player');
      audio.src = data.audio_url;
      
      // 3. Renderizar palavras
      const container = document.getElementById('text-container');
      data.words.forEach((word, index) => {
        const span = document.createElement('span');
        span.className = 'word';
        span.textContent = word.text;
        span.dataset.start = word.start;
        span.dataset.end = word.end;
        span.dataset.index = index;
        container.appendChild(span);
      });
      
      // 4. Sincronizar highlighting durante reprodução
      audio.addEventListener('timeupdate', () => {
        const currentTime = audio.currentTime;
        
        document.querySelectorAll('.word').forEach(span => {
          const start = parseFloat(span.dataset.start);
          const end = parseFloat(span.dataset.end);
          
          if (currentTime >= start && currentTime <= end) {
            span.classList.add('active');
          } else {
            span.classList.remove('active');
          }
        });
      });
      
      // 5. Play
      audio.play();
    }
    
    loadAndPlaySync();
  </script>
</body>
</html>
```

---

## 🔐 Baixar Áudio Autenticado

O `audio_url` retornado é um endpoint protegido. Use a mesma autenticação para baixá-lo:

### cURL
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://your-api.com/audio/tts_abc123.mp3" \
  -o audio.mp3
```

### Python
```python
response = requests.get(
    f"https://your-api.com{audio_url}",
    headers={"Authorization": f"Bearer {token}"}
)

with open("audio.mp3", "wb") as f:
    f.write(response.content)
```

---

## 🚀 Performance e Caching

### Sistema de Cache Duplo

1. **Cache de Áudio** (`tts_cache`)
   - Armazena MP3 gerados
   - Hash: `SHA256(text + lang + model + speed)`
   - Reutiliza áudio idêntico entre requisições

2. **Cache de Alinhamento** (`tts_alignment_cache`)
   - Armazena timestamps por palavra
   - Vinculado ao `cache_id` do áudio
   - Evita reprocessamento com Whisper

### Exemplo de Performance

| Cenário | Tempo Estimado |
|---------|---------------|
| Cache MISS (novo texto) | 3-8s (gera áudio + alinha) |
| Cache HIT (áudio + alinhamento) | <100ms |
| Cache HIT (apenas áudio) | 2-4s (apenas alinha) |

---

## ⚙️ Requisitos Técnicos

### Modelos Baixados Automaticamente

- **faster-whisper tiny** (~75MB)
  - Baixado na primeira requisição
  - Armazenado em `/app/.cache/whisper`
  - CPU-only (int8 quantização)

### Idiomas Suportados

| Idioma | MMS Code | Whisper ISO | Exemplo |
|--------|----------|-------------|---------|
| Hebraico | `heb` | `he` | בְּרֵאשִׁית |
| Grego | `ell` | `el` | Ἐν ἀρχῇ |
| Português | `por` | `pt` | No princípio |

### Preservação de Unicode

✅ **Preservado no retorno:**
- Hebraico: Niqqud (נִקּוּד) completo
- Grego: Acentos politônicos (πολυτονικό)
- Português: Acentuação (ção, ã, õ)

---

## 🐛 Troubleshooting

### Problema: `words: []` (array vazio)

**Possíveis causas:**
1. faster-whisper não instalado → Instale: `pip install faster-whisper`
2. Áudio muito curto (<0.5s) → Whisper não detecta palavras
3. Idioma não detectado → Verifique se `lang` está correto
4. Erro no modelo Whisper → Verifique logs do servidor

### Problema: Timestamps imprecisos

**Soluções:**
- Use `speed=1.0` (sem modificação de velocidade)
- Evite textos muito longos (quebrar em sentenças)
- Modelo `tiny` tem limitações → Considere `base` para produção

### Problema: Latência alta

**Otimizações:**
- Cache está funcionando? → Verifique `cache_hit: true`
- Áudio já foi gerado antes? → Alinhamento é reaproveitado
- Use `/speak` se não precisa de timestamps

---

## 📊 Comparação de Endpoints

| Feature | `/speak` | `/speak_sync` |
|---------|----------|---------------|
| Retorna áudio | ✅ MP3 direto | ✅ Via URL |
| Timestamps | ❌ | ✅ Por palavra |
| Latência | 0.5-3s | 3-8s (primeira vez) |
| Cache | ✅ | ✅ Duplo (áudio + timestamps) |
| Use case | Simples TTS | Karaoke, legendas, aprendizado |

---

## 🔮 Próximos Passos

1. **Integrar no frontend**: Use exemplo de highlighting
2. **Testar com textos reais**: Bíblia em hebraico/grego
3. **Monitorar cache hits**: Endpoint `/admin/cache/stats`
4. **Ajustar rate limits**: Se necessário para `/speak_sync`

---

## 📝 Notas de Implementação

- **Modelo tiny**: Balanceamento entre performance e acurácia
- **CPU-only**: Compatível com Oracle Free Tier
- **Graceful degradation**: API nunca falha, retorna `words: []` em caso de erro
- **Unicode preservado**: Matching fuzzy mantém diacríticos originais

---

**Documentação completa:** https://github.com/rodolfogoulart/mms_tts_api
