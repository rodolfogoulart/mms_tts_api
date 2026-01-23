# 🎙️ Hebrew & Greek TTS API (Sherpa-ONNX)

API de Text-to-Speech para **Hebraico, Grego e Português** usando **Sherpa-ONNX** com modelos MMS-TTS!

## 🚀 **Versão Sherpa-ONNX - Áudio Perfeito**

✨ **Principais características:**
- 🎵 **Qualidade perfeita**: Usa Sherpa-ONNX para pré-processamento correto
- 🔥 **Ultra-leve**: Docker image ~500MB (vs ~2.5GB PyTorch)
- ⚡ **Rápido**: Inferência otimizada com ONNX
- 💾 **Eficiente**: ~50-100MB de memória
- 🌍 **Multilíngue**: Hebraico, Grego e Português
- 🎯 **Fácil**: API simples com cache inteligente

## 🔧 **Por Que Sherpa-ONNX?**

Os modelos MMS-TTS do repositório `willwade/mms-tts-multilingual-models-onnx` foram **convertidos especificamente para Sherpa-ONNX**. Usar ONNX Runtime diretamente resulta em áudio com som de "vento" porque falta o pré-processamento essencial:
- ❌ **ONNX Runtime direto**: Som de vento/sopro (inútil)
- ✅ **Sherpa-ONNX**: Fala clara e inteligível (perfeito!)

Sherpa-ONNX aplica automaticamente:
- Conversão de caracteres para phonemes
- Inserção de blank tokens
- Normalização de texto
- Processamento correto de diacríticos (niqqud, acentos)

## ✨ **Novidade: Word-Level Alignment** 🎯

Suporte a **sincronização palavra-por-palavra**!

- 🎤 Endpoint `/speak_sync` retorna timestamps por palavra
- 🎨 Perfeito para karaoke-style highlighting
- 📖 Ideal para aplicativos de aprendizado de idiomas
- 🔤 Preserva Unicode (niqqud hebraico, acentos gregos)

**Documentação completa**: [`resources/WORD_ALIGNMENT_GUIDE.md`](resources/WORD_ALIGNMENT_GUIDE.md)

---

## 🌟 **Modelos Suportados**

### 1. **MMS-TTS Hebrew (Sherpa-ONNX)** 
- ✅ **Hebraico nativo** (`heb`)
- 🎯 Modelo otimizado para hebraico bíblico e moderno
- 📜 Suporte completo a niqqud (pontos vocálicos)
- 🚀 Tamanho: ~10-15MB
- ⚡ Fala clara e natural

### 2. **MMS-TTS Greek (Sherpa-ONNX)**
- ✅ **Grego nativo** (`ell`) 
- 🏛️ Modelo ONNX especializado para grego
- 📜 Suporte completo a caracteres gregos
- 🚀 Performance extrema (~10-15MB)
- ⚡ Inferência 3-5x mais rápida que PyTorch

### 3. **MMS-TTS Portuguese ONNX**
- ✅ **Português nativo** (`por`)
- 🇧🇷 Modelo ONNX especializado para português
- 🚀 Performance extrema (~10-15MB)
- ⚡ Inferência 3-5x mais rápida que PyTorch

**Fonte dos modelos**: [`willwade/mms-tts-multilingual-models-onnx`](https://huggingface.co/willwade/mms-tts-multilingual-models-onnx)

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

#### **Para Docker Compose Local (ONNX + GPU):**
Edite `docker-compose.local.yml`:
```yaml
environment:
  # ONNX Runtime (TTS)
  - ORT_TENSORRT_FP16_ENABLE=0        # Desabilitar TensorRT FP16
  - ORT_TENSORRT_ENGINE_CACHE_ENABLE=1 # Cache de engines
  
  # Whisper (Word Alignment)
  - WHISPER_DEVICE=cuda          # Usar GPU NVIDIA
  - WHISPER_COMPUTE_TYPE=float16 # Otimizado para GPU
  - WHISPER_MODEL=medium         # Alta acurácia (~1.5GB VRAM)
  - LOG_LEVEL=info               # debug, info, warning, error
```

#### **Para Docker Compose Produção (ONNX CPU):**
Use o `Dockerfile.coolify` com variáveis já configuradas:
```bash
export ORT_TENSORRT_FP16_ENABLE=0  # ONNX Runtime otimizações
export HF_HOME=/path/to/cache      # Cache dos modelos
```

#### **Configurações Whisper:**
| Variável | Valores | Descrição |
|----------|---------|-----------|
| `WHISPER_MODEL` | `tiny`, `base`, `small`, `medium`, `large` | Tamanho do modelo |
| `WHISPER_DEVICE` | `cpu`, `cuda` | Dispositivo de processamento |
| `WHISPER_COMPUTE_TYPE` | `int8`, `float16`, `float32` | Tipo de computação |

### Modelos em Cache
Os modelos ONNX são baixados automaticamente na primeira execução:
- `willwade/mms-tts-multilingual-models-onnx/heb` (~10-15MB)
- `willwade/mms-tts-multilingual-models-onnx/ell` (~10-15MB)
- `willwade/mms-tts-multilingual-models-onnx/por` (~10-15MB)
- `faster-whisper` (small: ~500MB, medium: ~1.5GB)

**Total para 3 idiomas**: ~30-45MB (vs ~108MB PyTorch) 🎉

## 🛠️ **Solução de Problemas**

### GPU NVIDIA não detectada (ONNX Runtime)
```bash
# 1. Verificar ONNX Runtime providers
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
# Deve mostrar: ['CUDAExecutionProvider', 'CPUExecutionProvider']

# 2. Se CUDA não aparecer, instalar onnxruntime-gpu
pip uninstall onnxruntime
pip install onnxruntime-gpu

# 3. Verificar CUDA no host
nvidia-smi

# 4. Fallback automático: Se GPU não disponível, usa CPU automaticamente
```

### Whisper GPU (Docker Compose Local)
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

## 📊 **Performance (ONNX)**

| Modelo | Idioma | Tamanho | Tempo/Frase (CPU) | Tempo/Frase (GPU) | Qualidade |
|--------|--------|---------|-------------------|-------------------|----------|
| MMS-TTS Hebrew ONNX | Hebraico | 10-15MB | ~0.5-1s | ~0.2-0.4s | ⭐⭐⭐⭐⭐ |
| MMS-TTS Greek ONNX | Grego | 10-15MB | ~0.5-1s | ~0.2-0.4s | ⭐⭐⭐⭐⭐ |
| MMS-TTS Portuguese ONNX | Português | 10-15MB | ~0.5-1s | ~0.2-0.4s | ⭐⭐⭐⭐⭐ |

**Nota**: Tempos 2-5x mais rápidos que versão PyTorch anterior!

## � **Links Úteis**

- 📖 [Documentação MMS](https://arxiv.org/abs/2305.13516)
- 🤗 [MMS-TTS ONNX Models](https://huggingface.co/willwade/mms-tts-multilingual-models-onnx)
- 🤗 [MMS-TTS Hebrew Original](https://huggingface.co/facebook/mms-tts-heb)
- 🤗 [MMS-TTS Greek Original](https://huggingface.co/facebook/mms-tts-ell)
- 🐳 [Docker Hub](https://hub.docker.com/)
- ⚡ [ONNX Runtime](https://onnxruntime.ai/)

## 📄 **Licença**

- **MMS-TTS Hebrew/Greek**: CC-BY-NC 4.0
- **Este projeto**: MIT

---