"""
Rate limiting module using slowapi.
Provides keying by authenticated user_id for protected endpoints,
and client IP address for unauthenticated endpoints.
"""
import logging
import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from config.settings import SECRET_KEY, JWT_ALGORITHM

logger = logging.getLogger(__name__)


def get_user_or_ip_key(request: Request) -> str:
    """
    Extract rate limit key:
    - Returns 'user:{user_id}' if a valid Authorization Bearer JWT token is present.
    - Falls back to client IP address (get_remote_address) for unauthenticated requests.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except jwt.PyJWTError:
            pass

    return get_remote_address(request)


# Limiter instance with in-memory storage (single-process MVP scope; scale out via Redis if needed)
limiter = Limiter(key_func=get_user_or_ip_key)
