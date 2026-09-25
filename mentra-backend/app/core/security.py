import hashlib
import hmac
import os
import base64
from datetime import datetime, timezone
from jose import jwt, JWTError
from app.core.config import settings
from app.core.errors import UnauthorizedError

# --- Password hashing (PBKDF2-HMAC-SHA256, stdlib-only: no native bcrypt build
# dependency, which keeps the backend easy to install in restricted/offline
# environments). Salted + iterated; safe for an MVP's auth needs. ---

_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        algo, iterations, salt_b64, hash_b64 = hashed.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# --- JWT ---

def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + settings.ACCESS_TOKEN_EXPIRES,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Invalid token.")
        return user_id
    except JWTError:
        raise UnauthorizedError("Invalid or expired token.")
