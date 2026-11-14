from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
import hashlib
import hmac
import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Konteks hashing password bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash dummy pre-computed untuk mitigasi serangan timing user enumeration
# Menggunakan hash bcrypt valid yang tidak cocok dengan password apa pun
DUMMY_PASSWORD_HASH = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"


def hash_password(password: str) -> str:
    """Melakukan hashing password menggunakan bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Memverifikasi kecocokan password polos terhadap hash bcrypt."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Membuat token JWT HS256 dengan klaim sub, exp, dan iat."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
    }
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Mendekode dan memvalidasi token JWT HS256."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])


def generate_ip_hash(ip_address: str) -> str:
    """Menghasilkan hash HMAC-SHA256 dari IP address menggunakan secret server."""
    secret = settings.JWT_SECRET.encode("utf-8")
    ip_bytes = (ip_address or "unknown").encode("utf-8")
    return hmac.new(secret, ip_bytes, hashlib.sha256).hexdigest()
