# 🚀 Quick Start - Forced Alignment

## Teste Rápido em 3 Passos

### 1. Iniciar a API 🔧

```bash
# Com Docker Compose
docker-compose -f docker-compose.local.yml up -d --build

# Aguardar inicialização (2-5 min na primeira vez)
docker logs -f aletheia-tts-local
```

**Aguarde ver:**
```
✅ faster-whisper 'small' model loaded successfully
✅ Whisper model ready for forced alignment
```

---

### 2. Testar com curl 🎯

```bash
# Hebraico - Gênesis 1:1
curl -X POST "http://localhost:8000/speak_sync" \
  -d "text=בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם" \
  -d "model=hebrew" \
  -d "return_audio=false" | jq .

# Grego - João 1:1
curl -X POST "http://localhost:8000/speak_sync" \
  -d "text=Ἐν ἀρχῇ ἦν ὁ λόγος" \
  -d "model=greek" \
  -d "return_audio=false" | jq .

# Português
curl -X POST "http://localhost:8000/speak_sync" \
  -d "text=O Senhor é o meu pastor" \
  -d "model=portuguese" \
  -d "return_audio=false" | jq .
```

---

### 3. Rodar testes automatizados 🧪

```bash
python test_forced_alignment.py
```

**Output esperado:**
```
✅ API está funcionando!
✅ Testando: Gênesis 1:1 (Hebraico)
📊 Estatísticas:
   - Duração do áudio: 3.25s
   - Total de palavras: 5
   - Palavras matched: 5
   - Taxa de match: 100.0%

💾 Áudio salvo: test_output/hebrew_genesis.mp3
📄 Timestamps salvos: test_output/hebrew_genesis_timestamps.json
📝 Legendas SRT salvas: test_output/hebrew_genesis.srt

🎯 Resultado Final: 3/3 testes passaram
✅ TODOS OS TESTES PASSARAM!
```

---

## 🎨 Demo Interativo

Abra no navegador:

```bash
# Abrir diretamente (se a API já está rodando)
start demo_forced_alignment.html  # Windows
open demo_forced_alignment.html   # macOS
xdg-open demo_forced_alignment.html  # Linux
```

**Ou servir via Python:**
```bash
python -m http.server 8080
# Abrir http://localhost:8080/demo_forced_alignment.html
```

**Recursos do demo:**
- ✨ Highlight palavra-por-palavra em tempo real
- 🎵 Player de áudio integrado
- 📊 Estatísticas visuais
- 🖱️ Click em palavras para pular
- 🌍 Suporte RTL/LTR

---

## 📊 Verificar Qualidade

### Output JSON Esperado

```json
{
  "text": "בְּרֵאשִׁית בָּרָא אֱלֹהִים",
  "word_timestamps": [
    {
      "text": "בְּרֵאשִׁית",
      "start": 0.0,
      "end": 0.82,
      "confidence": 1.0
    },
    {
      "text": "בָּרָא",
      "start": 0.82,
      "end": 1.24,
      "confidence": 0.98
    }
  ],
  "alignment_stats": {
    "total_words": 3,
    "matched_words": 3,
    "match_ratio": 1.0
  }
}
```

### Indicadores de Qualidade

| Match Ratio | Qualidade | Ação |
|-------------|-----------|------|
| ≥ 0.9 | ✅ EXCELENTE | Timestamps confiáveis |
| 0.7 - 0.9 | 🟡 BOA | Usar com confiança |
| 0.5 - 0.7 | ⚠️ RAZOÁVEL | Verificar palavras de baixa confiança |
| < 0.5 | ❌ BAIXA | Timestamps estimados (fallback) |

---

## 🐛 Troubleshooting

### "Word alignment feature not available"

**Problema:** faster-whisper não instalado

**Solução:**
```bash
pip install faster-whisper
# Ou rebuild container
docker-compose -f docker-compose.local.yml up -d --build
```

---

### Alinhamento de baixa qualidade

**Sintomas:**
- `match_ratio < 0.5`
- `confidence = 0.3` em muitas palavras
- Timestamps parecem uniformemente espaçados

**Causas:**
1. Áudio com ruído
2. Velocidade muito alta (`speed > 1.5`)
3. Modelo/idioma incorreto

**Soluções:**
```bash
# Reduzir velocidade
curl ... -d "speed=1.0"

# Verificar modelo correto
curl ... -d "model=hebrew"  # Para hebraico

# Usar modelo maior (local)
WHISPER_MODEL=medium docker-compose up
```

---

### API não responde

**Verificar:**
```bash
# Status do container
docker ps

# Logs
docker logs aletheia-tts-local

# Health check
curl http://localhost:8000/health
```

---

## 📈 Performance Esperada

### Oracle Free Tier (CPU)
- ⏱️ Tempo total: 1.2-2.5s
- 🎯 RTF: 0.5-1.0x
- 📊 Acurácia: 85-95%

### Notebook Local (GPU)
- ⏱️ Tempo total: 0.5-0.95s
- 🎯 RTF: 0.2-0.4x
- 📊 Acurácia: 90-98%

---

## 📚 Próximos Passos

1. ✅ **Teste básico** (este guia)
2. 📖 **Ler documentação completa**: [`FORCED_ALIGNMENT.md`](FORCED_ALIGNMENT.md)
3. 🔧 **Integrar no seu app**: Ver exemplos em Python/JavaScript
4. 🎨 **Customizar demo**: Adaptar HTML para suas necessidades

---

## 💡 Dicas

### Para Apps de Bíblia

```javascript
// Sincronizar highlight com áudio
audio.addEventListener('timeupdate', () => {
  const currentWord = findCurrentWord(audio.currentTime);
  highlightWord(currentWord.textStart, currentWord.textEnd);
});
```

### Para Análise de Pronúncia

```python
# Identificar palavras problemáticas
problematic = [
    w for w in word_timestamps 
    if w['confidence'] < 0.7
]
```

### Para Legendas

```python
# Gerar arquivo SRT
generate_srt(word_timestamps, 'output.srt')
```

---

## 🎉 Pronto!

Agora você tem forced alignment funcionando! 🚀

**Documentação completa**: [`FORCED_ALIGNMENT.md`](FORCED_ALIGNMENT.md)  
**Implementação detalhada**: [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md)
