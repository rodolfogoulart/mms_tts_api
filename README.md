# 🎙️ Hebrew & Greek TTS API

API especializada de Text-to-Speech focada em **Hebraico e Grego** usando modelos MMS-TTS do Meta/Facebook!

## 🌟 **Modelos Suportados**

### 1. **MMS-TTS Hebrew** (Meta/Facebook) 
- ✅ **Hebraico nativo** (`heb`)
- 🎯 Modelo especializado para hebraico
- 📜 Suporte completo a caracteres hebraicos
- 🚀 Alta qualidade e performance otimizada

### 2. **MMS-TTS Greek** (Meta/Facebook)
- ✅ **Grego nativo** (`ell`) 
- 🏛️ Modelo especializado para grego
- 📜 Suporte completo a caracteres gregos
- 🚀 Alta qualidade e performance otimizada

## 🚀 **Início Rápido**

### Docker (Recomendado)

```bash
# Build da imagem
docker build -t hebrew-greek-tts .

# Windows (PowerShell)
docker-compose up --build

# Executar API
docker run -p 8000:8000 hebrew-greek-tts

# Testar
curl http://localhost:8000/health
```

### Execução Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar API
python -m uvicorn app.multi_model_api:app --host 0.0.0.0 --port 8000

# Documentação interativa
open http://localhost:8000/docs
```

## 📚 **Exemplos de Uso**

### Hebraico
```bash
curl -X POST "http://localhost:8000/speak" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "text=שלום עולם, איך אתה היום?&lang=heb&model=hebrew" \
     --output hebrew_audio.mp3
```

### Grego  
```bash
curl -X POST "http://localhost:8000/speak" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "text=Γεια σας, πώς είστε σήμερα;&lang=ell&model=greek" \
     --output greek_audio.mp3
```

### Auto-detecção de Modelo
```bash
curl -X POST "http://localhost:8000/speak" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "text=שלום עולם&lang=heb" \
     --output auto_hebrew.mp3
```

## 🌍 **Idiomas Suportados**

| Código | Idioma | Modelo | Exemplo |
|--------|--------|--------|---------|
| `heb` | Hebraico | MMS-TTS Hebrew | שלום עולם |
| `ell` | Grego | MMS-TTS Greek | Γεια σας |

## 📋 **Endpoints da API**

### `POST /speak` - Gerar Áudio
**Parâmetros:**
- `text`: Texto para converter
- `lang`: Código do idioma (`heb` para hebraico, `ell` para grego)

### `GET /models` - Listar Modelos
```json
{
  "models": {
    "hebrew": {"name": "MMS-TTS Hebrew", "supported_languages": {"heb": "Hebrew"}},
    "greek": {"name": "MMS-TTS Greek", "supported_languages": {"ell": "Greek"}}
  }
}
```

### `GET /languages` - Listar Idiomas
```json
{
  "supported_languages": {
    "heb": {"name": "Hebrew", "model": "MMS-TTS Hebrew"},
    "ell": {"name": "Greek", "model": "MMS-TTS Greek"}
  },
  "total_languages": 2
}
```

### `GET /health` - Status da API
```json
{
  "status": "ok",
  "device": "cpu",
  "loaded_models": ["hebrew", "greek"]
}
```

## 🧪 **Testes**

### Teste Automatizado
```bash
python test_hebrew_greek.py
```

### Teste Manual - Hebraico
```bash
python -c "
import requests
response = requests.post('http://localhost:8000/speak', 
    data={'text': 'שלום עולם', 'lang': 'heb'})
with open('test_hebrew.mp3', 'wb') as f:
    f.write(response.content)
print('✅ Áudio em hebraico gerado: test_hebrew.mp3')
"
```

### Teste Manual - Grego
```bash
python -c "
import requests  
response = requests.post('http://localhost:8000/speak',
    data={'text': 'Γεια σας', 'lang': 'ell'})
with open('test_greek.mp3', 'wb') as f:
    f.write(response.content)
print('✅ Áudio em grego gerado: test_greek.mp3')
"
```

## 🔧 **Configuração Avançada**

### Variáveis de Ambiente
```bash
export CUDA_VISIBLE_DEVICES=0  # GPU específica
export HF_HOME=/path/to/cache  # Cache dos modelos
```

### Modelos em Cache
Os modelos são baixados automaticamente na primeira execução:
- `facebook/mms-tts-heb` (~36MB)
- `facebook/mms-tts-ell` (~36MB)

## � **Solução de Problemas**

### Erro: "python-multipart" 
```bash
docker build --no-cache -t hebrew-greek-tts .
```

### Modelos não carregam
```bash
# Verificar espaço em disco
df -h

# Limpar cache
rm -rf ~/.cache/huggingface/
```

### GPU não detectada
```bash
# Verificar CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Instalar CUDA version
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## 📊 **Performance**

| Modelo | Idioma | Tamanho | Tempo/Frase | Qualidade |
|--------|--------|---------|-------------|-----------|
| MMS-TTS Hebrew | Hebraico | 36MB | ~2-3s | ⭐⭐⭐⭐⭐ |
| MMS-TTS Greek | Grego | 36MB | ~2-3s | ⭐⭐⭐⭐⭐ |

## � **Links Úteis**

- 📖 [Documentação MMS](https://arxiv.org/abs/2305.13516)
- 🤗 [MMS-TTS Hebrew no HuggingFace](https://huggingface.co/facebook/mms-tts-heb)
- 🤗 [MMS-TTS Greek no HuggingFace](https://huggingface.co/facebook/mms-tts-ell)
- 🐳 [Docker Hub](https://hub.docker.com/)

## 📄 **Licença**

- **MMS-TTS Hebrew/Greek**: CC-BY-NC 4.0
- **Este projeto**: MIT

---