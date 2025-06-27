import psutil
import logging
import time
from fastapi import APIRouter

router = APIRouter()

# Configurar logging estruturado para Coolify
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/app/logs/app.log'),
        logging.StreamHandler()
    ]
)

@router.get("/metrics")
def get_metrics():
    """Métricas do sistema para monitoramento no Coolify"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "uptime": time.time() - psutil.boot_time(),
        "processes": len(psutil.pids())
    }

@router.get("/health/detailed")
def detailed_health():
    """Health check detalhado para debugging"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "system": {
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_free": psutil.disk_usage('/').free
        }
    }