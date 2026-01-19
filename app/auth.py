from fastapi import HTTPException, Security, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import secrets
import os
import logging
from functools import wraps

from .database import db_manager

logger = logging.getLogger(__name__)

# Configurações de segurança
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "hebrew-greek-tts-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "60"))

# Exportar para que outros módulos possam usar
__all__ = [
    'get_current_active_user',
    'get_admin_user', 
    'get_rate_limited_user',
    'create_access_token',
    'revoke_token',
    'AuthenticationError',
    'PermissionError',
    'ACCESS_TOKEN_EXPIRE_MINUTES'  # Adicionar à exportação
]

# Esquemas de segurança
security_bearer = HTTPBearer(auto_error=False)
security_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)

class AuthenticationError(HTTPException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class PermissionError(HTTPException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )

def create_access_token(user_data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> tuple[str, str]:
    """Cria token JWT e registra sessão no banco"""
    to_encode = user_data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Gerar JTI único para o token
    jti = secrets.token_urlsafe(32)
    
    to_encode.update({
        "exp": expire,
        "jti": jti,
        "iat": datetime.utcnow()
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # Registrar sessão no banco
    if 'user_id' in user_data:
        db_manager.create_session(
            user_id=user_data['user_id'],
            token_jti=jti,
            expires_at=expire
        )
    
    return encoded_jwt, jti

def verify_token(token: str) -> Dict[str, Any]:
    """Verifica e decodifica token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Verificar se token não foi revogado
        jti = payload.get('jti')
        if jti and not db_manager.is_token_valid(jti):
            raise AuthenticationError("Token has been revoked")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token expired")
    except jwt.JWTError:
        raise AuthenticationError("Invalid token")

def get_client_ip(request: Request) -> str:
    """Obtém IP do cliente"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def get_current_user(
    request: Request,
    bearer_token: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    api_key: Optional[str] = Security(security_api_key)
) -> Dict[str, Any]:
    """Obtém usuário atual via JWT ou API Key"""
    
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    
    # Tentar autenticação via API Key primeiro
    if api_key:
        try:
            api_key_data = db_manager.verify_api_key(api_key, ip_address)
            if api_key_data:
                return {
                    "type": "api_key",
                    "api_key_id": api_key_data["id"],
                    "name": api_key_data["name"],
                    "permissions": api_key_data["permissions"],
                    "rate_limit": api_key_data["rate_limit"],
                    "usage_count": api_key_data["usage_count"]
                }
        except Exception as e:
            logger.warning(f"API key verification failed: {e}")
    
    # Tentar autenticação via JWT
    if bearer_token:
        try:
            payload = verify_token(bearer_token.credentials)
            return {
                "type": "jwt",
                "user_id": payload.get("user_id"),
                "username": payload.get("sub"),
                "permissions": payload.get("permissions", []),
                "is_admin": payload.get("is_admin", False),
                "rate_limit": payload.get("rate_limit", 100),
                "exp": payload.get("exp"),
                "jti": payload.get("jti")
            }
        except Exception as e:
            logger.warning(f"JWT verification failed: {e}")
    
    raise AuthenticationError("No valid authentication provided")

# Dependências para diferentes níveis de acesso
async def get_current_active_user(request: Request, current_user: dict = Depends(get_current_user)):
    """Usuário autenticado básico"""
    return current_user

async def get_admin_user(request: Request, current_user: dict = Depends(get_current_user)):
    """Usuário com permissões de admin"""
    permissions = current_user.get("permissions", [])
    is_admin = current_user.get("is_admin", False)
    
    if "*" not in permissions and "admin" not in permissions and not is_admin:
        raise PermissionError("Admin permission required")
    
    return current_user

async def get_rate_limited_user(request: Request, current_user: dict = Depends(get_current_user)):
    """Usuário com verificação de rate limit"""
    
    # Identificador único por usuário
    if current_user["type"] == "api_key":
        identifier = f"api_key_{current_user['api_key_id']}"
    else:
        identifier = f"user_{current_user['user_id']}"
    
    rate_limit = current_user.get("rate_limit", 100)
    
    # Verificar rate limit
    allowed, current_count = db_manager.check_rate_limit(identifier, rate_limit)
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {rate_limit} requests per hour. Current: {current_count}"
        )
    
    # Adicionar informações de rate limit ao contexto do usuário
    current_user["rate_limit_current"] = current_count
    current_user["rate_limit_max"] = rate_limit
    
    return current_user

def revoke_token(jti: str):
    """Revoga token JWT"""
    db_manager.revoke_token(jti)