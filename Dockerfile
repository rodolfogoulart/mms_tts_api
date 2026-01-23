# Multi-stage build para reduzir tamanho final
FROM python:3.10-slim AS builder
# Instalar dependências de build apenas no estágio builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Criar ambiente virtual para isolamento
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ============================================
# Estágio final - imagem limpa e otimizada
# ============================================
FROM python:3.10-slim

# Instalar apenas dependências runtime essenciais
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Copiar ambiente virtual do builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Criar usuário não-root para segurança
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Copiar apenas o código necessário
COPY --chown=app:app app/ ./app/

# Criar diretórios necessários (incluir data)
RUN mkdir -p temp logs .cache/huggingface data

# Volume para persistir banco de dados
VOLUME ["/app/data"]

# Variáveis de ambiente para otimização
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/app/.cache/huggingface \
    ORT_TENSORRT_FP16_ENABLE=0 \
    ORT_TENSORRT_ENGINE_CACHE_ENABLE=1

# Criar diretórios de cache
RUN mkdir -p /home/app/.cache/huggingface \
             /home/app/.cache/onnx_models

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expor porta
EXPOSE 8000

# Comando otimizado com configurações de performance
CMD ["uvicorn", "app.multi_model_api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--access-log", \
     "--log-level", "info"]

# Labels otimizados
LABEL maintainer="Hebrew-Greek TTS API" \
      description="Ultra-lightweight Hebrew & Greek TTS API using MMS-TTS ONNX models" \
      version="3.0-onnx" \
      supported_languages="heb,ell,por" \
      base_image="python:3.10-slim" \
      runtime="onnxruntime" \
      model_size="~10-20MB per language" \
      build_date="2025-01-23"
