# 🎛️ Exemplos de Uso - Voice Presets (Simplificado para MMS-TTS)

## ⚠️ **Limitações dos Modelos MMS-TTS**

Os modelos `facebook/mms-tts-heb` e `facebook/mms-tts-ell` têm **limitações** nos parâmetros avançados:

- ✅ **Velocidade** (speed): Suportada através de pós-processamento
- ❌ **Variação de pronúncia** (noise_scale): Não suportada
- ❌ **Variação temporal** (noise_scale_w): Não suportada
- ❌ **Múltiplas vozes**: Não suportada

## 📚 Como usar os presets simplificados

### 1. **Usando Presets** (Recomendado)

#### 🎤 Voz Natural (Padrão)
```bash
curl -X POST "http://localhost:3000/speak" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "text=שלום עולם&lang=heb&preset=natural" \
     --output hebrew_natural.mp3
```

#### 🐌 Voz Lenta (Para Aprendizado)
```bash
curl -X POST "http://localhost:3000/speak" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "text=Γεια σας&lang=ell&preset=slow" \
     --output greek_slow.mp3
```

#### 🏃 Voz Rápida
```bash
curl -X POST "http://localhost:3000/speak" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "text=שלום עולם&lang=heb&preset=fast" \
     --output hebrew_fast.mp3
```

### 2. **Configuração Manual de Velocidade**

```bash
curl -X POST "http://localhost:3000/speak" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "text=שלום עולם&lang=heb&speed=1.3" \
     --output hebrew_slow_custom.mp3
```

### 3. **Presets Disponíveis**

```bash
curl http://localhost:3000/voice-presets
```

**Resposta:**
```json
{
  "presets": {
    "natural": {
      "description": "Voz natural balanceada",
      "length_scale": 1.0
    },
    "slow": {
      "description": "Fala lenta para aprendizado",
      "length_scale": 1.5
    },
    "fast": {
      "description": "Fala rápida",
      "length_scale": 0.7
    }
  },
  "note": "MMS-TTS models have limited parameter support. Only speed adjustment is available.",
  "available_parameters": ["speed"]
}
```

---

## ✅ **Testando a Correção**

Agora você pode testar novamente:

```bash
curl -X POST "http://localhost:3000/speak" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "text=Γεια σας&lang=ell&preset=slow" \
     --output greek_slow.mp3
```

Isso deve funcionar sem erros! 🎉
