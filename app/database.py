import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging
import os

logger = logging.getLogger(__name__)

# Configuração do banco
DB_PATH = os.getenv("DATABASE_PATH", "/app/data/tts_auth.db")
DB_DIR = os.path.dirname(DB_PATH)

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        # Criar diretório se não existir
        os.makedirs(DB_DIR, exist_ok=True)
        self.init_database()
    
    def get_connection(self):
        """Cria conexão com o banco"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Para acessar colunas por nome
        return conn
    
    def init_database(self):
        """Inicializa o banco de dados com as tabelas"""
        with self.get_connection() as conn:
            # Tabela de usuários
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    permissions TEXT NOT NULL DEFAULT '["tts", "models"]',
                    is_active BOOLEAN DEFAULT 1,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    rate_limit INTEGER DEFAULT 100
                )
            ''')
            
            # Tabela de API Keys
            conn.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT UNIQUE NOT NULL,
                    key_prefix TEXT NOT NULL,
                    name TEXT NOT NULL,
                    permissions TEXT NOT NULL DEFAULT '["tts", "models"]',
                    rate_limit INTEGER DEFAULT 100,
                    is_active BOOLEAN DEFAULT 1,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    last_used TIMESTAMP,
                    usage_count INTEGER DEFAULT 0,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')
            
            # Tabela de sessions/tokens JWT
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_jti TEXT UNIQUE NOT NULL,
                    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_revoked BOOLEAN DEFAULT 0,
                    user_agent TEXT,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Tabela de rate limiting
            conn.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT NOT NULL,
                    request_count INTEGER DEFAULT 1,
                    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(identifier, window_start)
                )
            ''')
            
            # Tabela de logs de auditoria
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    api_key_id INTEGER,
                    action TEXT NOT NULL,
                    resource TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    success BOOLEAN DEFAULT 1,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
                )
            ''')
            
            # Tabela de cache TTS
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tts_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text_hash TEXT NOT NULL,
                    text TEXT NOT NULL,
                    lang TEXT NOT NULL,
                    model TEXT NOT NULL,
                    speed REAL NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    hit_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(text_hash, lang, model, speed)
                )
            ''')
            
            # Índices para melhor performance
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tts_cache_hash 
                ON tts_cache(text_hash, lang, model, speed)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tts_cache_hit_count 
                ON tts_cache(hit_count)
            ''')
            
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
    
    def hash_password(self, password: str) -> tuple[str, str]:
        """Gera hash seguro da senha"""
        salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac('sha256', 
                                          password.encode('utf-8'), 
                                          salt.encode('utf-8'), 
                                          100000)
        return password_hash.hex(), salt
    
    def verify_password(self, password: str, password_hash: str, salt: str) -> bool:
        """Verifica senha"""
        test_hash = hashlib.pbkdf2_hmac('sha256',
                                       password.encode('utf-8'),
                                       salt.encode('utf-8'),
                                       100000)
        return test_hash.hex() == password_hash
    
    def create_user(self, username: str, password: str, email: str = None, 
                   permissions: List[str] = None, is_admin: bool = False,
                   rate_limit: int = 100) -> int:
        """Cria novo usuário"""
        password_hash, salt = self.hash_password(password)
        permissions = permissions or ["tts", "models"]
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO users (username, email, password_hash, salt, permissions, is_admin, rate_limit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (username, email, password_hash, salt, json.dumps(permissions), is_admin, rate_limit))
            
            user_id = cursor.lastrowid
            
            # Log de auditoria
            conn.execute('''
                INSERT INTO audit_logs (user_id, action, details)
                VALUES (?, 'user_created', ?)
            ''', (user_id, f"User {username} created"))
            
            conn.commit()
            logger.info(f"User created: {username} (ID: {user_id})")
            return user_id
    
    def authenticate_user(self, username: str, password: str, ip_address: str = None) -> Optional[Dict]:
        """Autentica usuário"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, username, email, password_hash, salt, permissions, is_active, is_admin, rate_limit
                FROM users WHERE username = ? AND is_active = 1
            ''', (username,))
            
            user = cursor.fetchone()
            if not user:
                # Log tentativa falhada
                conn.execute('''
                    INSERT INTO audit_logs (action, resource, ip_address, success, details)
                    VALUES ('login_attempt', ?, ?, 0, 'User not found')
                ''', (username, ip_address))
                conn.commit()
                return None
            
            if not self.verify_password(password, user['password_hash'], user['salt']):
                # Log senha incorreta
                conn.execute('''
                    INSERT INTO audit_logs (user_id, action, ip_address, success, details)
                    VALUES (?, 'login_attempt', ?, 0, 'Invalid password')
                ''', (user['id'], ip_address))
                conn.commit()
                return None
            
            # Atualizar último login
            conn.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user['id'],))
            
            # Log login bem-sucedido
            conn.execute('''
                INSERT INTO audit_logs (user_id, action, ip_address, success, details)
                VALUES (?, 'login_success', ?, 1, 'User authenticated')
            ''', (user['id'], ip_address))
            
            conn.commit()
            
            return {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'permissions': json.loads(user['permissions']),
                'is_admin': bool(user['is_admin']),
                'rate_limit': user['rate_limit']
            }
    
    def create_api_key(self, name: str, permissions: List[str] = None, 
                      rate_limit: int = 100, expires_days: int = None,
                      created_by: int = None) -> str:
        """Cria nova API key"""
        # Gerar chave aleatória
        api_key = f"tts_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_prefix = api_key[:8]
        
        permissions = permissions or ["tts", "models"]
        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO api_keys (key_hash, key_prefix, name, permissions, rate_limit, 
                                    created_by, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (key_hash, key_prefix, name, json.dumps(permissions), rate_limit, 
                  created_by, expires_at))
            
            api_key_id = cursor.lastrowid
            
            # Log de auditoria
            conn.execute('''
                INSERT INTO audit_logs (user_id, api_key_id, action, details)
                VALUES (?, ?, 'api_key_created', ?)
            ''', (created_by, api_key_id, f"API key {name} created"))
            
            conn.commit()
            logger.info(f"API key created: {name} (ID: {api_key_id})")
            
        return api_key
    
    def verify_api_key(self, api_key: str, ip_address: str = None) -> Optional[Dict]:
        """Verifica API key"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, name, permissions, rate_limit, is_active, expires_at, usage_count
                FROM api_keys 
                WHERE key_hash = ? AND is_active = 1
            ''', (key_hash,))
            
            api_key_data = cursor.fetchone()
            if not api_key_data:
                # Log tentativa falhada
                conn.execute('''
                    INSERT INTO audit_logs (action, resource, ip_address, success, details)
                    VALUES ('api_key_attempt', ?, ?, 0, 'Invalid API key')
                ''', (api_key[:8], ip_address))
                conn.commit()
                return None
            
            # Verificar expiração
            if api_key_data['expires_at']:
                expires_at = datetime.fromisoformat(api_key_data['expires_at'])
                if datetime.now() > expires_at:
                    conn.execute('''
                        INSERT INTO audit_logs (api_key_id, action, ip_address, success, details)
                        VALUES (?, 'api_key_attempt', ?, 0, 'API key expired')
                    ''', (api_key_data['id'], ip_address))
                    conn.commit()
                    return None
            
            # Atualizar estatísticas de uso
            conn.execute('''
                UPDATE api_keys 
                SET last_used = CURRENT_TIMESTAMP, usage_count = usage_count + 1
                WHERE id = ?
            ''', (api_key_data['id'],))
            
            # Log uso bem-sucedido
            conn.execute('''
                INSERT INTO audit_logs (api_key_id, action, ip_address, success, details)
                VALUES (?, 'api_key_used', ?, 1, 'API key authenticated')
            ''', (api_key_data['id'], ip_address))
            
            conn.commit()
            
            return {
                'id': api_key_data['id'],
                'name': api_key_data['name'],
                'permissions': json.loads(api_key_data['permissions']),
                'rate_limit': api_key_data['rate_limit'],
                'usage_count': api_key_data['usage_count']
            }
    
    def create_session(self, user_id: int, token_jti: str, expires_at: datetime,
                      user_agent: str = None, ip_address: str = None) -> int:
        """Cria sessão para JWT token"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO sessions (user_id, token_jti, expires_at, user_agent, ip_address)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, token_jti, expires_at, user_agent, ip_address))
            
            session_id = cursor.lastrowid
            conn.commit()
            return session_id
    
    def is_token_valid(self, token_jti: str) -> bool:
        """Verifica se token JWT é válido"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id FROM sessions 
                WHERE token_jti = ? AND is_revoked = 0 AND expires_at > CURRENT_TIMESTAMP
            ''', (token_jti,))
            
            return cursor.fetchone() is not None
    
    def revoke_token(self, token_jti: str):
        """Revoga token JWT"""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE sessions SET is_revoked = 1 WHERE token_jti = ?
            ''', (token_jti,))
            conn.commit()
    
    def check_rate_limit(self, identifier: str, limit: int, window_minutes: int = 60) -> tuple[bool, int]:
        """Verifica rate limit"""
        window_start = datetime.now() - timedelta(minutes=window_minutes)
        
        with self.get_connection() as conn:
            # Limpar entradas antigas
            conn.execute('''
                DELETE FROM rate_limits WHERE window_start < ?
            ''', (window_start,))
            
            # Contar requests na janela atual
            cursor = conn.execute('''
                SELECT COALESCE(SUM(request_count), 0) as total
                FROM rate_limits 
                WHERE identifier = ? AND window_start >= ?
            ''', (identifier, window_start))
            
            current_count = cursor.fetchone()['total']
            
            if current_count >= limit:
                return False, current_count
            
            # Incrementar contador
            hour_key = datetime.now().strftime("%Y-%m-%d-%H")
            conn.execute('''
                INSERT OR REPLACE INTO rate_limits (identifier, request_count, window_start)
                VALUES (?, COALESCE((SELECT request_count FROM rate_limits WHERE identifier = ? AND window_start = ?), 0) + 1, ?)
            ''', (f"{identifier}:{hour_key}", f"{identifier}:{hour_key}", hour_key, hour_key))
            
            conn.commit()
            return True, current_count + 1
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Estatísticas do usuário"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as login_count,
                    MAX(timestamp) as last_activity
                FROM audit_logs 
                WHERE user_id = ? AND action IN ('login_success', 'api_usage')
            ''', (user_id,))
            
            stats = cursor.fetchone()
            return {
                'login_count': stats['login_count'],
                'last_activity': stats['last_activity']
            }
    
    def get_cache_entry(self, text: str, lang: str, model: str, speed: float) -> Optional[Dict]:
        """Busca entrada no cache"""
        text_hash = hashlib.sha256(f"{text}{lang}{model}{speed}".encode()).hexdigest()
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, file_path, file_size, hit_count
                FROM tts_cache 
                WHERE text_hash = ? AND lang = ? AND model = ? AND speed = ?
            ''', (text_hash, lang, model, speed))
            
            entry = cursor.fetchone()
            if entry:
                # Verificar se arquivo ainda existe
                if os.path.exists(entry['file_path']):
                    # Incrementar hit_count e atualizar last_accessed
                    conn.execute('''
                        UPDATE tts_cache 
                        SET hit_count = hit_count + 1, last_accessed = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (entry['id'],))
                    conn.commit()
                    
                    logger.info(f"Cache HIT: {text[:50]}... (hits: {entry['hit_count'] + 1})")
                    return {
                        'id': entry['id'],
                        'file_path': entry['file_path'],
                        'file_size': entry['file_size'],
                        'hit_count': entry['hit_count'] + 1
                    }
                else:
                    # Arquivo não existe mais, remover do cache
                    conn.execute('DELETE FROM tts_cache WHERE id = ?', (entry['id'],))
                    conn.commit()
                    logger.warning(f"Cache entry removed (file not found): {entry['file_path']}")
            
            return None
    
    def save_cache_entry(self, text: str, lang: str, model: str, speed: float, 
                        file_path: str, file_size: int) -> int:
        """Salva entrada no cache"""
        text_hash = hashlib.sha256(f"{text}{lang}{model}{speed}".encode()).hexdigest()
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO tts_cache 
                (text_hash, text, lang, model, speed, file_path, file_size, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ''', (text_hash, text, lang, model, speed, file_path, file_size))
            
            cache_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Cache saved: {text[:50]}... -> {file_path}")
            return cache_id
    
    def get_cache_size(self) -> int:
        """Retorna tamanho total do cache em bytes"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT COALESCE(SUM(file_size), 0) as total FROM tts_cache')
            return cursor.fetchone()['total']
    
    def cleanup_cache(self, max_size_mb: int = 100) -> Dict:
        """Remove entradas menos acessadas quando cache ultrapassa o limite"""
        max_size_bytes = max_size_mb * 1024 * 1024
        current_size = self.get_cache_size()
        
        if current_size <= max_size_bytes:
            return {
                'cleaned': False,
                'current_size_mb': round(current_size / (1024 * 1024), 2),
                'max_size_mb': max_size_mb,
                'removed_count': 0
            }
        
        logger.info(f"Cache cleanup triggered: {current_size / (1024*1024):.2f}MB > {max_size_mb}MB")
        
        with self.get_connection() as conn:
            # Buscar entradas menos acessadas
            entries = conn.execute('''
                SELECT id, file_path, file_size, hit_count
                FROM tts_cache 
                ORDER BY hit_count ASC, last_accessed ASC
            ''').fetchall()
            
            removed_count = 0
            freed_size = 0
            
            for entry in entries:
                if current_size - freed_size <= max_size_bytes:
                    break
                
                # Deletar arquivo
                if os.path.exists(entry['file_path']):
                    try:
                        os.remove(entry['file_path'])
                        logger.info(f"Removed cache file: {entry['file_path']} (hits: {entry['hit_count']})")
                    except Exception as e:
                        logger.error(f"Error removing cache file: {e}")
                
                # Remover do banco
                conn.execute('DELETE FROM tts_cache WHERE id = ?', (entry['id'],))
                freed_size += entry['file_size']
                removed_count += 1
            
            conn.commit()
            
            new_size = self.get_cache_size()
            logger.info(f"Cache cleaned: removed {removed_count} entries, freed {freed_size / (1024*1024):.2f}MB")
            
            return {
                'cleaned': True,
                'current_size_mb': round(new_size / (1024 * 1024), 2),
                'max_size_mb': max_size_mb,
                'removed_count': removed_count,
                'freed_mb': round(freed_size / (1024 * 1024), 2)
            }
    
    def get_cache_stats(self) -> Dict:
        """Retorna estatísticas do cache"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_entries,
                    SUM(file_size) as total_size,
                    SUM(hit_count) as total_hits,
                    AVG(hit_count) as avg_hits,
                    MAX(hit_count) as max_hits
                FROM tts_cache
            ''')
            
            stats = cursor.fetchone()
            
            # Top 5 mais acessados
            top_hits = conn.execute('''
                SELECT text, lang, model, speed, hit_count, last_accessed
                FROM tts_cache 
                ORDER BY hit_count DESC 
                LIMIT 5
            ''').fetchall()
            
            return {
                'total_entries': stats['total_entries'] or 0,
                'total_size_mb': round((stats['total_size'] or 0) / (1024 * 1024), 2),
                'total_hits': stats['total_hits'] or 0,
                'avg_hits': round(stats['avg_hits'] or 0, 2),
                'max_hits': stats['max_hits'] or 0,
                'top_entries': [{
                    'text': entry['text'][:50] + '...',
                    'lang': entry['lang'],
                    'model': entry['model'],
                    'speed': entry['speed'],
                    'hit_count': entry['hit_count'],
                    'last_accessed': entry['last_accessed']
                } for entry in top_hits]
            }
    
    def initialize_default_data(self):
        """Inicializa dados padrão usando variáveis de ambiente"""
        try:
            # Dados do usuário admin via env vars
            admin_username = os.getenv("ADMIN_USERNAME", "admin")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
            admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
            admin_rate_limit = int(os.getenv("ADMIN_RATE_LIMIT", "1000"))
            
            # Dados do usuário demo via env vars
            demo_username = os.getenv("DEMO_USERNAME", "user")
            demo_password = os.getenv("DEMO_PASSWORD", "user123")
            demo_email = os.getenv("DEMO_EMAIL", "user@example.com")
            demo_rate_limit = int(os.getenv("DEMO_RATE_LIMIT", "100"))
            
            # Configurações de API Keys
            create_demo_api_key = os.getenv("CREATE_DEMO_API_KEY", "true").lower() == "true"
            create_admin_api_key = os.getenv("CREATE_ADMIN_API_KEY", "true").lower() == "true"
            
            demo_api_key_name = os.getenv("DEMO_API_KEY_NAME", "Demo Key")
            admin_api_key_name = os.getenv("ADMIN_API_KEY_NAME", "Admin Key")
            
            # Verificar se deve criar usuários padrão
            create_default_users = os.getenv("CREATE_DEFAULT_USERS", "true").lower() == "true"
            
            results = {}
            
            if create_default_users:
                # Criar usuário admin
                try:
                    admin_id = self.create_user(
                        username=admin_username,
                        password=admin_password,
                        email=admin_email,
                        permissions=["*"],
                        is_admin=True,
                        rate_limit=admin_rate_limit
                    )
                    results["admin_user"] = {
                        "id": admin_id,
                        "username": admin_username,
                        "email": admin_email,
                        "credentials": f"{admin_username}/{admin_password}",
                        "note": "CHANGE PASSWORD IN PRODUCTION!"
                    }
                    logger.info(f"Admin user created: {admin_username}")
                except Exception as e:
                    logger.warning(f"Admin user creation failed (may already exist): {e}")
                    results["admin_user"] = {"error": str(e)}
                
                # Criar usuário demo
                try:
                    demo_id = self.create_user(
                        username=demo_username,
                        password=demo_password,
                        email=demo_email,
                        permissions=["tts", "models"],
                        is_admin=False,
                        rate_limit=demo_rate_limit
                    )
                    results["demo_user"] = {
                        "id": demo_id,
                        "username": demo_username,
                        "email": demo_email,
                        "credentials": f"{demo_username}/{demo_password}"
                    }
                    logger.info(f"Demo user created: {demo_username}")
                except Exception as e:
                    logger.warning(f"Demo user creation failed (may already exist): {e}")
                    results["demo_user"] = {"error": str(e)}
            
            # Criar API Keys se solicitado
            if create_demo_api_key:
                try:
                    demo_key = self.create_api_key(
                        name=demo_api_key_name,
                        permissions=["tts", "models"],
                        rate_limit=int(os.getenv("DEMO_API_KEY_RATE_LIMIT", "50"))
                    )
                    results["demo_api_key"] = {
                        "key": demo_key,
                        "name": demo_api_key_name,
                        "permissions": ["tts", "models"],
                        "usage": f"curl -H 'X-API-Key: {demo_key}' https://your-api.com/speak"
                    }
                    logger.info(f"Demo API Key created: {demo_api_key_name}")
                except Exception as e:
                    logger.warning(f"Demo API key creation failed: {e}")
                    results["demo_api_key"] = {"error": str(e)}
            
            if create_admin_api_key:
                try:
                    admin_key = self.create_api_key(
                        name=admin_api_key_name,
                        permissions=["*"],
                        rate_limit=int(os.getenv("ADMIN_API_KEY_RATE_LIMIT", "1000"))
                    )
                    results["admin_api_key"] = {
                        "key": admin_key,
                        "name": admin_api_key_name,
                        "permissions": ["*"],
                        "usage": f"curl -H 'X-API-Key: {admin_key}' https://your-api.com/admin/users"
                    }
                    logger.info(f"Admin API Key created: {admin_api_key_name}")
                except Exception as e:
                    logger.warning(f"Admin API key creation failed: {e}")
                    results["admin_api_key"] = {"error": str(e)}
            
            # Informações adicionais
            results["configuration"] = {
                "create_default_users": create_default_users,
                "create_demo_api_key": create_demo_api_key,
                "create_admin_api_key": create_admin_api_key,
                "database_path": self.db_path
            }
            
            logger.info("Default data initialization completed")
            return results
            
        except Exception as e:
            logger.error(f"Error during default data initialization: {e}")
            return {"error": str(e)}

# Instância global do gerenciador
db_manager = DatabaseManager()