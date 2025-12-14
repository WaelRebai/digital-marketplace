from fastapi import Request, Response, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import re
import html

# --- Rate Limiting ---
# Initialize Limiter
limiter = Limiter(key_func=get_remote_address)

def setup_rate_limiting(app: FastAPI):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Security Headers Middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security Headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none';"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

# --- Input Sanitization ---
def sanitize_input(text: str) -> str:
    """
    Sanitize input string:
    - HTML escape
    - Strip whitespace
    """
    if not isinstance(text, str):
        return text
    
    # Strip whitespace
    clean_text = text.strip()
    
    # HTML Escape
    clean_text = html.escape(clean_text)
    
    return clean_text

def validate_password_strength(password: str) -> bool:
    """
    Validate password strength:
    - Min 8 chars
    - At least one uppercase
    - At least one lowercase
    - At least one digit
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    return True
