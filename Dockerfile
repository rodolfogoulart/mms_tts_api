# Build ultra-otimizado para VPS com recursos limitados
FROM python:3.10-slim AS builder

# Instalar apenas o essencial para build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Criar ambiente virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar dependências com limites de memória
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# Estágio final - Produção Ultra-Leve
# ============================================
FROM python:3.10-slim

# Instalar apenas o mínimo necessário
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copiar ambiente virtual
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Usuário não-root
RUN useradd --create-home --uid 1000 app
USER app
WORKDIR /home/app

# Copiar código
COPY --chown=app:app app/ ./app/

# Diretórios mínimos
RUN mkdir -p temp .cache/huggingface

# Variáveis ultra-otimizadas para VPS limitado
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/app/.cache/huggingface \
    CUDA_VISIBLE_DEVICES="" \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    TORCH_NUM_THREADS=1 \
    PORT=3000

# Health check simples
HEALTHCHECK --interval=120s --timeout=30s --start-period=180s --retries=2 \
    CMD curl -f http://localhost:3000/health || exit 1

EXPOSE 3000

# Comando corrigido com sintaxe adequada
CMD ["python", "-m", "uvicorn", "app.multi_model_api:app", "--host", "0.0.0.0", "--port", "3000", "--workers", "1", "--log-level", "warning"]
