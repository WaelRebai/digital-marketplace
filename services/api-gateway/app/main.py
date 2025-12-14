import os
import time
import logging
from datetime import datetime
import json
from shared.logging_config import setup_logging, RequestLoggingMiddleware
from shared.security_config import SecurityHeadersMiddleware

# Configuration
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
PRODUCTS_SERVICE_URL = os.getenv("PRODUCTS_SERVICE_URL", "http://products-service:8002")
ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders-service:8003")
PAYMENTS_SERVICE_URL = os.getenv("PAYMENTS_SERVICE_URL", "http://payments-service:8004")

# Setup Logging
logger = setup_logging("api-gateway")

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="API Gateway")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Middleware
app.add_middleware(RequestLoggingMiddleware, service_name="api-gateway")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Middleware ---

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - Status: {response.status_code} - "
        f"Duration: {process_time:.4f}s"
    )
    return response

# Auth Check Helper
async def verify_token(request: Request):
    # Public routes
    path = request.url.path
    if path in ["/api/auth/login", "/api/auth/register", "/health", "/docs", "/openapi.json"]:
        return None

    auth_header = request.headers.get("Authorization")
    if not auth_header:
         raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Verify with Auth Service
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AUTH_SERVICE_URL}/verify", headers={"Authorization": auth_header})
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                 raise HTTPException(status_code=401, detail="Invalid token")
            return data["data"] # User context
        except httpx.HTTPStatusError:
             raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        except httpx.RequestError:
             raise HTTPException(status_code=503, detail="Auth service unavailable")

# --- Proxy Logic ---

async def forward_request(service_url: str, request: Request, path: str):
    client = httpx.AsyncClient()
    try:
        # Prepare headers
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        # Inject Correlation ID
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            headers["X-Request-ID"] = request_id

        # Verify Auth (Middleware-like check)
        # ... context verification ...
        try:
            user = await verify_token(request)
            if user:
                 headers["x-user-id"] = user["sub"]
                 headers["x-user-role"] = user["role"]
        except HTTPException as e:
            return Response(content=e.detail, status_code=e.status_code)

        # Prepare content
        content = await request.body()
        
        # Forward
        url = f"{service_url}{path}"
        if request.url.query:
            url += f"?{request.url.query}"

        # Log Outgoing Call
        start_time = time.time()
        logger.info(f"Calling Downstream Service", extra={
            "target": service_url,
            "path": path,
            "method": request.method,
            "request_id": request_id
        })

        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=content,
            timeout=10.0
        )
        
        duration = (time.time() - start_time) * 1000
        logger.info(f"Downstream Call Completed", extra={
            "target": service_url,
            "path": path,
            "status": resp.status_code,
            "duration_ms": round(duration, 2),
            "request_id": request_id
        })
        
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers)
        )
    except httpx.RequestError:
        return Response(content="Service Unavailable", status_code=503)
    finally:
        await client.aclose()

# --- Routes ---

@app.get("/health") # Returns JSON directly, schema variable
async def health_check():
    # Helper to check service
    async def check_service(url, name):
        start = time.time()
        status_val = "unhealthy"
        details = None
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{url}/health", timeout=2.0)
                if res.status_code == 200:
                    status_val = "healthy"
                    details = res.json()
                else:
                    details = {"error": f"Status {res.status_code}"}
        except Exception as e:
            status_val = "unreachable"
            details = {"error": str(e)}
        
        return {
            "service": name,
            "status": status_val,
            "latency": f"{time.time() - start:.4f}s",
            "details": details
        }

    # Parallel checks
    import asyncio
    results = await asyncio.gather(
        check_service(AUTH_SERVICE_URL, "auth-service"),
        check_service(PRODUCTS_SERVICE_URL, "products-service"),
        check_service(ORDERS_SERVICE_URL, "orders-service"),
        check_service(PAYMENTS_SERVICE_URL, "payments-service")
    )

    overall_status = "healthy"
    for r in results:
        if r["status"] != "healthy":
            overall_status = "unhealthy"
            break
    
    response_data = {
        "service": "api-gateway",
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": results
    }

    if overall_status == "unhealthy":
        # We return 503 but body contains details
         return Response(
             content=json.dumps(response_data), 
             status_code=503, 
             media_type="application/json"
         )

    return response_data

# 1. Auth Service
@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@limiter.limit("100/minute")
async def auth_proxy(request: Request, path: str):
    # Strip /api/auth prefix logic: handled by path param?
    # request path: /api/auth/login. 'path' param captures 'login'.
    # Target: auth-service/login.
    return await forward_request(AUTH_SERVICE_URL, request, f"/{path}")

# 2. Products Service
@app.api_route("/api/products{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@limiter.limit("100/minute")
async def products_proxy(request: Request, path: str):
    # Path captures remaining. If /api/products, path is "".
    # If /api/products/123, path is "/123".
    # Target: products-service/products....
    # Wait, my logic was: Strip /api.
    # If request is /api/products, I want /products.
    # Here path is "". So I send "/". Products service needs "/products".
    # So I must PREPEND "/products" if I use this route matcher?
    # NO. The simplest is: /api/products -> products-service/products.
    # path matches "" (empty). Target becomes .../products + "" = .../products.
    # If /api/products/123 -> path is "/123". Target .../products/123.
    # This works IF I append "/products".
    return await forward_request(PRODUCTS_SERVICE_URL, request, f"/products{path}")

@app.api_route("/api/categories{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@limiter.limit("100/minute")
async def categories_proxy(request: Request, path: str):
    # /api/categories -> products-service/categories
    return await forward_request(PRODUCTS_SERVICE_URL, request, f"/categories{path}")

# 3. Orders Service
@app.api_route("/api/orders{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@limiter.limit("100/minute")
async def orders_proxy(request: Request, path: str):
    # /api/orders -> orders-service/orders
    return await forward_request(ORDERS_SERVICE_URL, request, f"/orders{path}")

@app.api_route("/api/cart{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@limiter.limit("100/minute")
async def cart_proxy(request: Request, path: str):
    # /api/cart -> orders-service/cart
    return await forward_request(ORDERS_SERVICE_URL, request, f"/cart{path}")

# 4. Payments Service
@app.api_route("/api/payments{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@limiter.limit("100/minute")
async def payments_proxy(request: Request, path: str):
    # /api/payments -> payments-service/payments
    return await forward_request(PAYMENTS_SERVICE_URL, request, f"/payments{path}")
