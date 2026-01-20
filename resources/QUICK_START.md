# 🚀 Quick Start - Word Alignment Feature

## 🎯 Para que serve?

Endpoint `/speak_sync` retorna áudio + timestamps palavra-por-palavra para criar experiências interativas tipo karaoke.

---

## ⚡ Uso Rápido

### Python
```python
import requests

# 1. Login
response = requests.post("https://api.com/auth/login", 
    data={"username": "admin", "password": "senha"})
token = response.json()["access_token"]

# 2. Gerar áudio + timestamps
response = requests.post("https://api.com/speak_sync",
    headers={"Authorization": f"Bearer {token}"},
    data={"text": "בְּרֵאשִׁית בָּרָא", "lang": "heb"})

result = response.json()
print(f"Audio: {result['audio_url']}")
for word in result['words']:
    print(f"{word['text']}: {word['start']}-{word['end']}s")
```

### cURL
```bash
# Login
TOKEN=$(curl -s -X POST "https://api.com/auth/login" \
  -F "username=admin" -F "password=senha" | jq -r .access_token)

# Sync request
curl -X POST "https://api.com/speak_sync" \
  -H "Authorization: Bearer $TOKEN" \
  -F "text=בְּרֵאשִׁית בָּרָא" \
  -F "lang=heb"
```

---

## 📤 Resposta

```json
{
  "audio_url": "/audio/tts_abc123.mp3",
  "language": "heb",
  "words": [
    {"text": "בְּרֵאשִׁית", "start": 0.12, "end": 0.55},
    {"text": "בָּרָא", "start": 0.60, "end": 0.92}
  ],
  "word_count": 2,
  "alignment_available": true
}
```

---

## 🎨 Frontend - Karaoke Highlighting

```javascript
// Fazer request
const response = await fetch('/speak_sync', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: new FormData([
    ['text', 'בְּרֵאשִׁית בָּרָא'],
    ['lang', 'heb']
  ])
});

const data = await response.json();

// Renderizar palavras
data.words.forEach(word => {
  const span = document.createElement('span');
  span.textContent = word.text;
  span.dataset.start = word.start;
  span.dataset.end = word.end;
  container.appendChild(span);
});

// Sincronizar com áudio
audio.addEventListener('timeupdate', () => {
  document.querySelectorAll('span').forEach(span => {
    if (audio.currentTime >= span.dataset.start && 
        audio.currentTime <= span.dataset.end) {
      span.classList.add('active'); // Highlight!
    } else {
      span.classList.remove('active');
    }
  });
});
```

---

## 🆚 /speak vs /speak_sync

| Feature | `/speak` | `/speak_sync` |
|---------|----------|---------------|
| Retorna | MP3 direto | JSON + URL |
| Timestamps | ❌ | ✅ |
| Latência | 0.5-3s | 3-8s |
| Use case | TTS simples | Karaoke, legendas |

---

## 🔧 Configurações

### Idiomas Suportados
- `heb` - Hebraico (com niqqud)
- `ell` - Grego (com acentos)
- `por` - Português

### Parâmetros Opcionais
- `speed`: 0.1-3.0 (padrão: 1.0)
- `preset`: "natural", "slow", "fast"
- `model`: "auto" (recomendado)

---

## 🐛 Troubleshooting

**Problema**: `words: []` (vazio)
- ✅ faster-whisper instalado?
- ✅ Áudio > 0.5s?
- ✅ Idioma correto?

**Problema**: Latência alta
- ✅ Cache ativado? (verificar `cache_hit: true`)
- ✅ Usar `/speak` se não precisa timestamps

---

## 📚 Documentação Completa

- **Guia Detalhado**: `resources/WORD_ALIGNMENT_GUIDE.md`
- **Implementação**: `resources/IMPLEMENTATION_SUMMARY.md`
- **Teste**: `resources/test_speak_sync.py`

---

## 🏃 Deploy Rápido

```bash
# 1. Build
docker build -f Dockerfile.coolify -t mms-tts:latest .

# 2. Run
docker run -d -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=senha \
  mms-tts:latest

# 3. Test
curl http://localhost:8000/health
```

---

**API Version**: 3.1.0  
**Novo endpoint**: `POST /speak_sync`  
**Status**: ✅ Pronto para produção
