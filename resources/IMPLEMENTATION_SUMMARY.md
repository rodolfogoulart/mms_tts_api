# ✅ Word-Level Alignment Implementation - Summary

## 📌 O que foi implementado?

Novo endpoint `/speak_sync` que:
- ✅ Gera áudio TTS exatamente como `/speak`
- ✅ Adiciona alinhamento palavra-por-palavra com timestamps
- ✅ Preserva Unicode (niqqud hebraico, acentos gregos)
- ✅ Retorna JSON com URL do áudio + array de palavras
- ✅ Graceful degradation: retorna `words: []` se falhar
- ✅ Sistema de cache duplo (áudio + alinhamento)

---

## 📁 Arquivos Criados/Modificados

### 🆕 Novos Arquivos

1. **`app/word_alignment.py`**
   - Módulo principal de alinhamento
   - Função `align_words(audio_path, text, lang)`
   - Usa `faster-whisper` tiny model (CPU-only)
   - Fuzzy matching com preservação de Unicode
   - Validação de timestamps

2. **`resources/WORD_ALIGNMENT_GUIDE.md`**
   - Documentação completa do endpoint
   - Exemplos de uso (cURL, Python, JavaScript)
   - Frontend integration (karaoke-style highlighting)
   - Troubleshooting guide

3. **`resources/test_speak_sync.py`**
   - Script de teste automatizado
   - Testa hebraico, grego e português
   - Valida cache performance
   - Verifica download de áudio

### 📝 Arquivos Modificados

4. **`requirements.txt`**
   - ➕ `faster-whisper>=0.10.0,<1.1.0`

5. **`app/database.py`**
   - ➕ Tabela `tts_alignment_cache`
   - ➕ `get_alignment_cache(cache_id)`
   - ➕ `save_alignment_cache(cache_id, words)`
   - ➕ Índice `idx_alignment_cache_id`

6. **`app/multi_model_api.py`**
   - ➕ Constante `WHISPER_LANG_MAP` (mapeamento de idiomas)
   - ➕ Endpoint `POST /speak_sync` (linha ~520)
   - ➕ Endpoint `GET /audio/{filename}` (serve áudio autenticado)
   - 🔄 Atualizado `@app.get("/")` com documentação do novo endpoint

7. **`Dockerfile.coolify`**
   - ➕ Diretório `/app/.cache/whisper` criado no entrypoint
   - ➕ Permissões para `app:app` no cache do Whisper
   - ➕ Variável `WHISPER_CACHE_DIR=/app/.cache/whisper`

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────┐
│  Cliente (Frontend/API)                         │
└──────────────┬──────────────────────────────────┘
               │ POST /speak_sync
               │ (text, lang, speed, ...)
               ▼
┌─────────────────────────────────────────────────┐
│  FastAPI Endpoint (/speak_sync)                 │
│  - Autenticação JWT/API Key                     │
│  - Rate Limiting                                │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────┐
│  1. GERAÇÃO DE ÁUDIO                            │
│  ┌─────────────────────────────────────┐        │
│  │ Verificar cache de áudio (DB)       │        │
│  │ ✓ Cache HIT → Usar MP3 existente    │        │
│  │ ✗ Cache MISS:                        │        │
│  │   - Carregar modelo MMS-TTS          │        │
│  │   - Gerar áudio WAV                  │        │
│  │   - Converter para MP3               │        │
│  │   - Salvar em /cache/tts_*.mp3      │        │
│  │   - Registrar no tts_cache (DB)     │        │
│  └─────────────────────────────────────┘        │
└──────────────┬──────────────────────────────────┘
               │ audio_path, cache_id
               ▼
┌─────────────────────────────────────────────────┐
│  2. ALINHAMENTO DE PALAVRAS                     │
│  ┌─────────────────────────────────────┐        │
│  │ Verificar cache alignment (DB)      │        │
│  │ ✓ Cache HIT → Usar words[] existente│        │
│  │ ✗ Cache MISS:                        │        │
│  │   - Carregar faster-whisper (lazy)   │        │
│  │   - Transcrever com word_timestamps  │        │
│  │   - Fuzzy matching com texto original│        │
│  │   - Preservar Unicode (niqqud/acentos)│       │
│  │   - Salvar em tts_alignment_cache    │        │
│  └─────────────────────────────────────┘        │
└──────────────┬──────────────────────────────────┘
               │ words: [{text, start, end}, ...]
               ▼
┌─────────────────────────────────────────────────┐
│  3. RESPOSTA JSON                               │
│  {                                              │
│    "audio_url": "/audio/tts_*.mp3",            │
│    "language": "heb",                           │
│    "words": [...],                              │
│    "alignment_available": true,                 │
│    "cache_hit": false                           │
│  }                                              │
└─────────────────────────────────────────────────┘
```

---

## 🗄️ Schema do Banco de Dados

### Nova Tabela: `tts_alignment_cache`

```sql
CREATE TABLE tts_alignment_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_id INTEGER NOT NULL,              -- FK para tts_cache.id
    words_json TEXT NOT NULL,               -- JSON: [{text, start, end}, ...]
    alignment_model TEXT NOT NULL           -- 'faster-whisper-tiny'
        DEFAULT 'faster-whisper-tiny',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cache_id) REFERENCES tts_cache (id) ON DELETE CASCADE,
    UNIQUE(cache_id)
);

CREATE INDEX idx_alignment_cache_id ON tts_alignment_cache(cache_id);
```

### Exemplo de `words_json`:
```json
[
  {"text": "בְּרֵאשִׁית", "start": 0.12, "end": 0.55},
  {"text": "בָּרָא", "start": 0.60, "end": 0.92},
  {"text": "אֱלֹהִים", "start": 0.98, "end": 1.34}
]
```

---

## 🧪 Como Testar?

### 1. Instalar Dependências

```bash
cd /Users/rodolfo.goulart/development/aletheia/mms_tts_api
pip install -r requirements.txt
```

Isso instalará `faster-whisper>=0.10.0`.

### 2. Executar API Localmente

```bash
python -m uvicorn app.multi_model_api:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Rodar Script de Teste

```bash
# Editar credenciais no script primeiro!
nano resources/test_speak_sync.py
# Alterar USERNAME e PASSWORD

# Executar
python resources/test_speak_sync.py
```

### 4. Teste Manual com cURL

```bash
# 1. Login
curl -X POST "http://localhost:8000/auth/login" \
  -F "username=admin" \
  -F "password=yourPassword"

# Copiar o access_token da resposta

# 2. Testar /speak_sync
curl -X POST "http://localhost:8000/speak_sync" \
  -H "Authorization: Bearer SEU_TOKEN_AQUI" \
  -F "text=בְּרֵאשִׁית בָּרָא אֱלֹהִים" \
  -F "lang=heb" \
  -F "speed=1.0"

# Resposta esperada:
# {
#   "audio_url": "/audio/tts_abc123.mp3",
#   "language": "heb",
#   "words": [
#     {"text": "בְּרֵאשִׁית", "start": 0.12, "end": 0.55},
#     ...
#   ],
#   "word_count": 3,
#   "alignment_available": true
# }

# 3. Baixar áudio
curl -H "Authorization: Bearer SEU_TOKEN_AQUI" \
  "http://localhost:8000/audio/tts_abc123.mp3" \
  -o teste.mp3
```

---

## 🐳 Deploy no Docker/Coolify

### 1. Build da Imagem

```bash
docker build -f Dockerfile.coolify -t mms-tts-api:latest .
```

### 2. Executar Container

```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=yourPassword \
  -e AUTO_INIT_DEFAULT_DATA=true \
  --name mms-tts-api \
  mms-tts-api:latest
```

### 3. Verificar Logs

```bash
docker logs -f mms-tts-api
```

Procurar por:
```
INFO: Loading faster-whisper tiny model (CPU-only)...
INFO: faster-whisper model loaded successfully
```

---

## 📊 Performance Esperada

### Oracle Free Tier (1 CPU, 1GB RAM)

| Cenário | Tempo |
|---------|-------|
| **Cache HIT completo** | ~100ms |
| **Cache HIT (só áudio)** | 2-4s (apenas alignment) |
| **Cache MISS completo** | 5-10s (áudio + alignment) |

### Primeira Requisição (Download de Modelos)

- **MMS-TTS** (facebook/mms-tts-heb): ~150MB
- **faster-whisper tiny**: ~75MB
- **Tempo total**: 3-5 min (só primeira vez)

---

## ⚠️ Notas Importantes

### 1. Graceful Degradation

Se `faster-whisper` falhar:
- ✅ Áudio é gerado normalmente
- ✅ Resposta retorna `words: []`
- ✅ Campo `alignment_available: false`
- ❌ Não lança exceção

### 2. Preservação de Unicode

- ✅ Hebraico: Niqqud preservado (`בְּרֵאשִׁית`)
- ✅ Grego: Acentos preservados (`Ἐν ἀρχῇ`)
- ✅ Matching fuzzy ignora diacríticos para comparação
- ✅ Texto original retornado no campo `text`

### 3. Segurança

- ✅ Endpoint `/speak_sync` requer autenticação
- ✅ Endpoint `/audio/{filename}` requer autenticação
- ✅ Validação de filename (previne path traversal)
- ✅ Rate limiting aplicado

### 4. Cache Automático

- ✅ Cache de áudio: Baseado em hash SHA256
- ✅ Cache de alignment: Vinculado ao cache_id
- ✅ Limpeza automática a cada 30 minutos
- ✅ Limite de 100MB (configurável)

---

## 🚀 Próximos Passos

### Curto Prazo
1. ✅ **Testar localmente** com script `test_speak_sync.py`
2. ✅ **Deploy no Coolify** e monitorar logs
3. ✅ **Integrar no frontend** usando exemplo do guia

### Médio Prazo
4. 🔄 **Otimizar modelo**: Considerar `faster-whisper base` se precisão for insuficiente
5. 🔄 **Adicionar métricas**: Monitorar acurácia do alignment
6. 🔄 **Documentar API**: Adicionar ao Swagger/OpenAPI

### Longo Prazo
7. 💡 **Fine-tuning**: Treinar Whisper específico para hebraico/grego bíblico
8. 💡 **Caching inteligente**: Pré-processar versículos populares
9. 💡 **Melhorar matching**: Usar embeddings ao invés de fuzzy matching

---

## 📞 Suporte

- **Documentação Completa**: `resources/WORD_ALIGNMENT_GUIDE.md`
- **Script de Teste**: `resources/test_speak_sync.py`
- **Logs do Sistema**: `/app/logs/app.log` (no container)
- **Repositório**: https://github.com/rodolfogoulart/mms_tts_api

---

## ✅ Checklist de Implementação

- [x] Adicionar `faster-whisper` ao requirements.txt
- [x] Criar módulo `app/word_alignment.py`
- [x] Estender schema do banco com `tts_alignment_cache`
- [x] Adicionar mapeamento `WHISPER_LANG_MAP`
- [x] Implementar endpoint `/speak_sync`
- [x] Adicionar endpoint `/audio/{filename}`
- [x] Atualizar Dockerfile.coolify
- [x] Criar documentação completa
- [x] Criar script de teste
- [x] Validar código (sem erros de lint)

**Status: 🟢 IMPLEMENTAÇÃO COMPLETA**

---

**Implementado em**: 20 de janeiro de 2026  
**Versão da API**: 3.1.0  
**Tempo de Implementação**: ~45 minutos
