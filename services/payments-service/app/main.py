from fastapi import FastAPI, Depends, HTTPException, status, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import os
import sys
import httpx
import uuid
import asyncio
import random
from bson import ObjectId

# Add the parent directory to sys.path to resolve shared imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.utils import (
    get_db_client, settings, SuccessResponse, ErrorResponse, 
    NotFoundException, UnauthorizedException, AppException,
    HealthResponse
)
from shared.logging_config import setup_logging, RequestLoggingMiddleware
from shared.security_config import setup_rate_limiting, SecurityHeadersMiddleware, limiter

from app.schemas import PaymentProcess, PaymentResponse
from app.models import PaymentDB

# Setup Logging
logger = setup_logging("payments-service")

app = FastAPI(title="Payments Service")

# Security Setup
setup_rate_limiting(app)
app.add_middleware(SecurityHeadersMiddleware)

# Configuration
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders-service:8003")

# Middleware
app.add_middleware(RequestLoggingMiddleware, service_name="payments-service")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_client():
    app.mongodb_client = get_db_client()
    app.mongodb = app.mongodb_client.payments_db
    # Indexes
    await app.mongodb.payments.create_index("order_id", unique=True)
    await app.mongodb.payments.create_index("user_id")

@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_client.close()

# --- Dependencies ---
async def get_current_user(request: Request, authorization: str = Header(...)):
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Authorization": authorization}
            request_id = getattr(request.state, "request_id", None)
            if request_id:
                headers["X-Request-ID"] = request_id
            
            response = await client.get(f"{AUTH_SERVICE_URL}/verify", headers=headers)
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                raise UnauthorizedException("Invalid token")
            return data["data"]
        except httpx.RequestError:
            raise AppException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth service unavailable")
        except httpx.HTTPStatusError:
             raise UnauthorizedException("Invalid authentication credentials")

async def get_order_details(order_id: str, authorization: str, request_id: Optional[str] = None):
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Authorization": authorization}
            if request_id:
                headers["X-Request-ID"] = request_id
                
            response = await client.get(f"{ORDERS_SERVICE_URL}/orders/{order_id}", headers=headers)
            if response.status_code == 404:
                raise NotFoundException("Order not found")
            response.raise_for_status()
            data = response.json()
            return data["data"]
        except httpx.HTTPStatusError:
             raise HTTPException(status_code=400, detail="Could not verify order")
        except httpx.RequestError:
            raise AppException(status.HTTP_503_SERVICE_UNAVAILABLE, "Orders service unavailable")

async def update_order_status(order_id: str, status: str, payment_id: str, request_id: Optional[str] = None):
    async with httpx.AsyncClient() as client:
        try:
            # Requires internal call. Since we are simulating, we assume no auth or we'd pass a service token. 
            headers = {}
            if request_id:
                headers["X-Request-ID"] = request_id
                
            payload = {"status": status, "payment_id": payment_id}
            response = await client.put(f"{ORDERS_SERVICE_URL}/orders/{order_id}/status", json=payload, headers=headers)
            response.raise_for_status()
        except httpx.RequestError:
            # Log error - inconsistency risk
            print(f"Failed to update order {order_id} status to {status}")
            pass

# --- Helper ---
def str_to_oid(id: str):
    try:
        return ObjectId(id)
    except:
        raise NotFoundException("Invalid ID format")

# --- Endpoints ---

@app.post("/payments/process", response_model=SuccessResponse[PaymentResponse])
@limiter.limit("10/minute")
async def process_payment(payment_request: PaymentProcess, request: Request, authorization: str = Header(...)):
    # 1. Verify Authentication
    user = await get_current_user(request, authorization)
    user_id = user["sub"]
    
    request_id = getattr(request.state, "request_id", None)

    # 2. Idempotency Check
    existing_payment = await app.mongodb.payments.find_one({"order_id": payment_request.order_id})
    if existing_payment:
         # Return existing receipt if completed
         existing_payment["id"] = str(existing_payment["_id"])
         return SuccessResponse(data=PaymentResponse(**existing_payment), message="Payment already processed")

    # 3. Verify Order & Get Amount
    order = await get_order_details(payment_request.order_id, authorization, request_id)
    if order["status"] != "pending":
         raise HTTPException(status_code=400, detail=f"Order is {order['status']}, cannot process payment")
    
    amount = Decimal(str(order["total_amount"])) # Ensure decimal precision

    # 4. Simulate Processing
    await asyncio.sleep(2) # 2 seconds delay
    
    # 90% Success Rate
    is_success = random.random() < 0.9
    status_val = "completed" if is_success else "failed"
    transaction_id = str(uuid.uuid4())

    # 5. Record Payment
    payment_db = PaymentDB(
        order_id=payment_request.order_id,
        user_id=user_id,
        amount=amount,
        status=status_val,
        transaction_id=transaction_id,
        payment_method=payment_request.payment_method,
        processed_at=datetime.utcnow()
    )
    # Handle Decimal for Mongo (convert to float or Decimal128)
    payment_dict = payment_db.dict(by_alias=True)
    payment_dict["amount"] = float(payment_dict["amount"])
    
    new_payment = await app.mongodb.payments.insert_one(payment_dict)
    
    # 6. Update Order Status
    # Call orders-service
    order_status = "completed" if is_success else "cancelled" # Prompt said "failure -> cancelled"
    await update_order_status(payment_request.order_id, order_status, str(new_payment.inserted_id), request_id)

    # Response
    created_payment = await app.mongodb.payments.find_one({"_id": new_payment.inserted_id})
    created_payment["id"] = str(created_payment["_id"])
    
    msg = "Payment successful" if is_success else "Payment failed"
    return SuccessResponse(data=PaymentResponse(**created_payment), message=msg)

@app.get("/payments/order/{order_id}", response_model=SuccessResponse[PaymentResponse])
@limiter.limit("10/minute")
async def get_payment_by_order(order_id: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    payment = await app.mongodb.payments.find_one({"order_id": order_id})
    if not payment:
        raise NotFoundException("Payment not found")
    
    if payment["user_id"] != user_id:
         raise UnauthorizedException("Not authorized to view this payment")

    payment["id"] = str(payment["_id"])
    return SuccessResponse(data=PaymentResponse(**payment))

@app.get("/payments/{payment_id}", response_model=SuccessResponse[PaymentResponse])
@limiter.limit("10/minute")
async def get_payment(payment_id: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    payment = await app.mongodb.payments.find_one({"_id": str_to_oid(payment_id)})
    if not payment:
        raise NotFoundException("Payment not found")
    
    if payment["user_id"] != user_id:
         raise UnauthorizedException("Not authorized to view this payment")

    payment["id"] = str(payment["_id"])
    return SuccessResponse(data=PaymentResponse(**payment))

@app.get("/payments/user", response_model=SuccessResponse[List[PaymentResponse]])
@limiter.limit("10/minute")
async def get_user_payments(request: Request, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    cursor = app.mongodb.payments.find({"user_id": user_id}).sort("created_at", -1)
    payments = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        payments.append(PaymentResponse(**doc))
    return SuccessResponse(data=payments)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "unhealthy"
    auth_status = "unknown"
    order_status = "unknown"
    
    # Check DB
    try:
        await app.mongodb_client.admin.command('ping')
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Check Auth Service
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{AUTH_SERVICE_URL}/health", timeout=2.0)
            if resp.status_code == 200:
                auth_status = "healthy"
            else:
                auth_status = "unhealthy"
        except Exception:
            auth_status = "unreachable"

    # Check Orders Service
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{ORDERS_SERVICE_URL}/health", timeout=2.0)
            if resp.status_code == 200:
                order_status = "healthy"
            else:
                order_status = "unhealthy"
        except Exception:
            order_status = "unreachable"

    overall_status = "healthy" if db_status == "connected" and auth_status == "healthy" and order_status == "healthy" else "unhealthy"
    
    if overall_status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unhealthy"
        )

    return HealthResponse(
        service="payments-service",
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        database=db_status,
        dependencies={
            "auth-service": auth_status,
            "orders-service": order_status
        }
    )
