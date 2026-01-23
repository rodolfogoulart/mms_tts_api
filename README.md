# 🎙️ Hebrew & Greek TTS API

API especializada de Text-to-Speech focada em **Hebraico e Grego** usando modelos MMS-TTS do Meta/Facebook!

## ✨ **Novidade: Word-Level Alignment** 🎯

Agora com suporte a **sincronização palavra-por-palavra**!

- 🎤 Endpoint `/speak_sync` retorna timestamps por palavra
- 🎨 Perfeito para karaoke-style highlighting
- 📖 Ideal para aplicativos de aprendizado de idiomas
- 🔤 Preserva Unicode (niqqud hebraico, acentos gregos)

**Documentação completa**: [`resources/WORD_ALIGNMENT_GUIDE.md`](resources/WORD_ALIGNMENT_GUIDE.md)

---

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

### 3. **MMS-TTS Portuguese** (Meta/Facebook)
- ✅ **Português nativo** (`por`)
- 🇧🇷 Modelo especializado para português
- 🚀 Alta qualidade e performance otimizada

## 🚀 **Início Rápido**

### Docker Compose (Recomendado)

#### **🖥️ Desenvolvimento Local com GPU NVIDIA**
Para rodar no seu notebook/desktop com GPU NVIDIA:

```bash
# Pré-requisito: NVIDIA Container Toolkit instalado
# Verificar GPU disponível
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Build e iniciar com GPU CUDA
docker-compose -f docker-compose.local.yml up --build

# Rodar em background
docker-compose -f docker-compose.local.yml up -d

# Ver logs em tempo real
docker-compose -f docker-compose.local.yml logs -f

# Parar
docker-compose -f docker-compose.local.yml down

# Testar
curl http://localhost:8000/health
```

**Configurações GPU (docker-compose.local.yml):**
- ✅ Whisper model: `medium` (~1.5GB VRAM, 90-98% acurácia)
- ✅ Device: `cuda` (GPU NVIDIA)
- ✅ Compute type: `float16` (otimizado para GPU)
- ✅ Fallback automático para CPU caso CUDA não disponível

#### **☁️ Produção VPS/Cloud (CPU)**
Para rodar em VPS sem GPU (ex: Oracle Cloud):

```bash
# Build e iniciar (CPU-only)
docker-compose up --build

# Rodar em background
docker-compose up -d

# Testar
curl http://localhost:8000/health
```

**Configurações CPU (Dockerfile.coolify):**
- ✅ Whisper model: `small` (~500MB, 85-95% acurácia)
- ✅ Device: `cpu` (ARM64 otimizado)
- ✅ Compute type: `int8` (quantização para economia de memória)

### Docker Manual

```bash
# Build da imagem
docker build -t hebrew-greek-tts .

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

#### **Para Docker Compose Local (GPU):**
Edite `docker-compose.local.yml`:
```yaml
environment:
  - WHISPER_DEVICE=cuda          # Usar GPU NVIDIA
  - WHISPER_COMPUTE_TYPE=float16 # Otimizado para GPU
  - WHISPER_MODEL=medium         # Alta acurácia (~1.5GB VRAM)
  - LOG_LEVEL=info               # debug, info, warning, error
```

#### **Para Docker Compose Produção (CPU):**
Use o `Dockerfile.coolify` com variáveis já configuradas:
```bash
export CUDA_VISIBLE_DEVICES=0  # GPU específica (se disponível)
export HF_HOME=/path/to/cache  # Cache dos modelos
```

#### **Configurações Whisper:**
| Variável | Valores | Descrição |
|----------|---------|-----------|
| `WHISPER_MODEL` | `tiny`, `base`, `small`, `medium`, `large` | Tamanho do modelo |
| `WHISPER_DEVICE` | `cpu`, `cuda` | Dispositivo de processamento |
| `WHISPER_COMPUTE_TYPE` | `int8`, `float16`, `float32` | Tipo de computação |

### Modelos em Cache
Os modelos são baixados automaticamente na primeira execução:
- `facebook/mms-tts-heb` (~36MB)
- `facebook/mms-tts-ell` (~36MB)
- `faster-whisper` (small: ~500MB, medium: ~1.5GB)

## 🛠️ **Solução de Problemas**

### GPU NVIDIA não detectada (Docker Compose Local)
```bash
# 1. Verificar NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# 2. Se não instalado, instalar NVIDIA Container Toolkit
# Ubuntu/Debian:
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 3. Verificar CUDA no host
nvidia-smi

# 4. Fallback automático: Se GPU não disponível, usa CPU automaticamente
```

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

# Limpar volumes Docker
docker-compose -f docker-compose.local.yml down -v
```

### Whisper model muito lento
```bash
# Reduzir tamanho do modelo
# Edite docker-compose.local.yml:
environment:
  - WHISPER_MODEL=small  # Ao invés de medium
  - WHISPER_COMPUTE_TYPE=int8  # Ao invés de float16
```

### GPU não detectada (execução local)
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