# Teste Sherpa-ONNX - Guia Simplificado

## 🚀 Como Testar

### Passo 1: Build e Start

```powershell
# Limpar containers antigos
docker-compose -f docker-compose.local.yml down

# Build e start
docker-compose -f docker-compose.local.yml up -d --build

# Ver logs
docker-compose -f docker-compose.local.yml logs -f
```

Aguarde ver no log:
```
INFO: Loading Sherpa-ONNX model: hebrew (heb)
INFO: Model loaded in X.XXs
INFO: Application startup complete.
```

### Passo 2: Executar Testes

```powershell
# Instalar requests (se necessário)
pip install requests

# Executar testes
python test_docker_sherpa.py
```

### Passo 3: Verificar Resultados

Os arquivos MP3 serão salvos em `./docker_test_output/`:
- `test_portuguese_sherpa.mp3` ✅ Fala clara
- `test_hebrew_sherpa.mp3` ✅ Fala clara  
- `test_greek_sherpa.mp3` ✅ Fala clara

**Ouça os arquivos!** A qualidade deve ser perfeita.

## 🔍 Testes Manuais com curl

```powershell
# Testar Português
curl -X POST "http://localhost:8000/speak" `
  -F "text=No princípio, Deus criou os céus e a terra." `
  -F "model=portuguese" `
  -F "speed=1.0" `
  -F "output_format=mp3" `
  --output test_pt.mp3

# Testar Hebraico
curl -X POST "http://localhost:8000/speak" `
  -F "text=בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ" `
  -F "model=hebrew" `
  -F "speed=1.0" `
  -F "output_format=mp3" `
  --output test_he.mp3
```

## 📊 Endpoints

- `GET /health` - Status (deve retornar `"engine": "sherpa-onnx"`)
- `GET /models` - Lista modelos disponíveis
- `POST /speak` - Gerar áudio
  - `text`: Texto para converter
  - `model`: hebrew, greek ou portuguese
  - `speed`: 0.5-2.0 (padrão: 1.0)
  - `output_format`: mp3 ou wav

## 🛑 Parar

```powershell
docker-compose -f docker-compose.local.yml down
```

## ✅ O Que Mudou

**Antes (ONNX Runtime)**: Som de vento ❌  
**Agora (Sherpa-ONNX)**: Fala clara ✅

Os modelos MMS-TTS do repositório `willwade/mms-tts-multilingual-models-onnx` foram convertidos especificamente para Sherpa-ONNX e precisam da biblioteca `sherpa-onnx` para funcionar corretamente.

## 📚 Mais Informações

- `COMPARACAO_ONNX_vs_SHERPA.md` - Análise técnica detalhada
- `IMPLEMENTACAO_SHERPA_RESUMO.md` - Resumo da implementação
