# Multi-stage build otimizado para Coolify/VPS
FROM python:3.10-slim AS builder

# Instalar dependências de build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Criar ambiente virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar dependências Python com otimizações
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# ============================================
# Estágio final - Produção
# ============================================
FROM python:3.10-slim

# Instalar apenas runtime essenciais + otimizações para VPS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Copiar ambiente virtual
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Criar usuário não-root
RUN useradd --create-home --shell /bin/bash --uid 1000 app
USER app
WORKDIR /home/app

# Copiar código
COPY --chown=app:app app/ ./app/

# Criar diretórios necessários
RUN mkdir -p temp logs .cache/huggingface .cache/transformers .cache/torch

# Variáveis otimizadas para VPS/Coolify
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    HF_HOME=/home/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/app/.cache/transformers \
    TORCH_HOME=/home/app/.cache/torch \
    CUDA_VISIBLE_DEVICES="" \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2

# Health check otimizado
HEALTHCHECK --interval=60s --timeout=15s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Comando otimizado para produção
CMD ["uvicorn", "app.multi_model_api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-log", \
     "--log-level", "info", \
     "--loop", "uvloop", \
     "--http", "httptools"]

# Labels para Coolify
LABEL org.opencontainers.image.title="Hebrew-Greek TTS API" \
      org.opencontainers.image.description="Lightweight Hebrew & Greek TTS API using MMS-TTS models" \
      org.opencontainers.image.version="2.1" \
      org.opencontainers.image.source="https://github.com/rodolfogoulart/mms_tts_api" \
      coolify.enabled="true" \
      coolify.port="8000" \
      coolify.healthcheck="/health"
