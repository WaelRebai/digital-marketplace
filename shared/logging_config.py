import logging
import json
import time
import sys
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from datetime import datetime
import traceback

# Sensitive headers to mask
SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key"}

class JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        if hasattr(record, "method"):
            log_obj["method"] = record.method
        if hasattr(record, "path"):
            log_obj["path"] = record.path
        if hasattr(record, "status_code"):
            log_obj["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = record.duration_ms
        if hasattr(record, "headers"):
            log_obj["headers"] = record.headers
            
        # Exception Info
        if record.exc_info:
            log_obj["exception"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(log_obj)

def setup_logging(service_name: str):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # clear existing handlers
    if logger.handlers:
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = JSONFormatter(service_name)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logging.getLogger(service_name)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service_name: str):
        super().__init__(app)
        self.logger = logging.getLogger(service_name)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Correlation ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Inject into request state so endpoints can access it
        request.state.request_id = request_id
        
        # Start Timer
        start_time = time.time()
        
        # Add Request ID to Response Headers
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            duration = (time.time() - start_time) * 1000
            self.log_request(request, 500, duration, request_id, exc_info=sys.exc_info())
            raise e

        # Calculate Duration
        duration = (time.time() - start_time) * 1000
        
        # Log Request
        self.log_request(request, response.status_code, duration, request_id)
        
        response.headers["X-Request-ID"] = request_id
        return response

    def log_request(self, request: Request, status_code: int, duration: float, request_id: str, exc_info=None):
        # Mask Headers
        headers = {}
        for k, v in request.headers.items():
            if k.lower() not in SENSITIVE_HEADERS:
                headers[k] = v
            else:
                headers[k] = "***"

        # User ID (if available in headers from Gateway or locally set state)
        # Gateway sets x-user-id
        user_id = request.headers.get("x-user-id")

        extra = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(duration, 2),
            "headers": headers,
            "user_id": user_id
        }
        
        if status_code >= 500:
            self.logger.error("Request Failed", extra=extra, exc_info=exc_info)
        elif status_code >= 400:
            self.logger.warning("Request Error", extra=extra)
        else:
            self.logger.info("Request Processed", extra=extra)
