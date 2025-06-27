import psutil
import logging
import time
import os
from fastapi import APIRouter

router = APIRouter()

# Configurar logging estruturado (com fallback para quando diretório não existe)
log_dir = "/home/app/logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'app.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@router.get("/metrics")
def get_metrics():
    """Métricas do sistema para monitoramento no Coolify"""
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "uptime": time.time() - psutil.boot_time(),
            "processes": len(psutil.pids()),
            "status": "ok"
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/health/detailed")
def detailed_health():
    """Health check detalhado para debugging"""
    try:
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "system": {
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "disk_free": psutil.disk_usage('/').free
            }
        }
    except Exception as e:
        logger.error(f"Error in detailed health check: {e}")
        return {
            "status": "error",
            "timestamp": time.time(),
            "error": str(e)
        }