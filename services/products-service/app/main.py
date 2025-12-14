from fastapi import FastAPI, Depends, HTTPException, status, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
import os
import sys
import httpx
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

from app.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListResponse, 
    CategoryCreate, CategoryResponse
)
from app.models import ProductDB, CategoryDB

# Setup Logging
logger = setup_logging("products-service")

app = FastAPI(title="Products Service")

# Security Setup
setup_rate_limiting(app)
app.add_middleware(SecurityHeadersMiddleware)

# Middleware
app.add_middleware(RequestLoggingMiddleware, service_name="products-service")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")

@app.on_event("startup")
async def startup_db_client():
    app.mongodb_client = get_db_client()
    app.mongodb = app.mongodb_client.products_db
    # Indexes
    await app.mongodb.products.create_index([("name", "text"), ("description", "text")])
    await app.mongodb.categories.create_index("slug", unique=True)

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
            return data["data"] # Returns payload dict
        except httpx.RequestError:
            raise AppException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth service unavailable")
        except httpx.HTTPStatusError:
             raise UnauthorizedException("Invalid authentication credentials")

# --- Helper ---
def str_to_oid(id: str):
    try:
        return ObjectId(id)
    except:
        raise NotFoundException("Invalid ID format")

# --- Endpoints ---

# Products
@app.get("/products", response_model=SuccessResponse[ProductListResponse])
@limiter.limit("60/minute")
async def list_products(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    search: Optional[str] = None
):
    query = {"is_active": True}
    if category:
        query["category"] = category
    
    price_query = {}
    if min_price:
        price_query["$gte"] = Decimal(min_price) # Decimal128 convert in motor? Motor uses Decimal128 for Decimals usually, or user needs generic float. Let's rely on standard pydantic decimal for now, but mongo stores as Decimal128 or double. 
        # Simpler for now: Convert to float for query if no Decimal128 support configured, but best practice is Decimal128. 
        # I'll convert to float for simplicity in this prototype as Mongo regex/float matching is easier without explicit Codec.
        price_query["$gte"] = float(min_price)
    if max_price:
         price_query["$lte"] = float(max_price)
    if price_query:
        query["price"] = price_query

    if search:
        query["name"] = {"$regex": search, "$options": "i"}

    skip = (page - 1) * limit
    total = await app.mongodb.products.count_documents(query)
    cursor = app.mongodb.products.find(query).skip(skip).limit(limit)
    products_docs = await cursor.to_list(length=limit)

    products = []
    for doc in products_docs:
        doc["id"] = str(doc["_id"])
        products.append(ProductResponse(**doc))

    return SuccessResponse(data=ProductListResponse(
        products=products,
        total=total,
        page=page,
        limit=limit
    ))

@app.get("/products/{product_id}", response_model=SuccessResponse[ProductResponse])
@limiter.limit("60/minute")
async def get_product(product_id: str, request: Request):
    product = await app.mongodb.products.find_one({"_id": str_to_oid(product_id), "is_active": True})
    if not product:
        raise NotFoundException("Product not found")
    product["id"] = str(product["_id"])
    return SuccessResponse(data=ProductResponse(**product))

@app.post("/products", response_model=SuccessResponse[ProductResponse])
@limiter.limit("60/minute")
async def create_product(product: ProductCreate, request: Request, user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise UnauthorizedException("Only vendors can create products")

    # Verify category existence
    cat = await app.mongodb.categories.find_one({"slug": product.category})
    if not cat:
        raise HTTPException(status_code=400, detail=f"Invalid category: '{product.category}' not found")

    product_db = ProductDB(
        vendor_id=user["sub"],
        **product.dict()
    )
    # Convert Decimal to float for storage (simple approach) or use BSON Decimal128. 
    # To run effectively without complex Codec setup, using float for price in storage is safer for this prototype.
    product_dict = product_db.dict(by_alias=True, exclude={"id"})
    product_dict["price"] = float(product_dict["price"])

    new_product = await app.mongodb.products.insert_one(product_dict)
    created_product = await app.mongodb.products.find_one({"_id": new_product.inserted_id})
    created_product["id"] = str(created_product["_id"])
    
    return SuccessResponse(data=ProductResponse(**created_product), message="Product created successfully")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "unhealthy"
    auth_status = "unknown"
    
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

    overall_status = "healthy" if db_status == "connected" and auth_status == "healthy" else "unhealthy"
    
    if overall_status == "unhealthy":
        logger.error(f"Health Check Failed: DB={db_status}, Auth={auth_status}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service Unhealthy: DB={db_status}, Auth={auth_status}"
        )

    return HealthResponse(
        service="products-service",
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        database=db_status,
        dependencies={
            "auth-service": auth_status
        }
    )

@app.put("/products/{product_id}", response_model=SuccessResponse[ProductResponse])
async def update_product(product_id: str, product_update: ProductUpdate, user: dict = Depends(get_current_user)):
    product = await app.mongodb.products.find_one({"_id": str_to_oid(product_id), "is_active": True})
    if not product:
        raise NotFoundException("Product not found")
    
    if product["vendor_id"] != user["sub"]:
        raise UnauthorizedException("Not authorized to update this product")

    update_data = {k: v for k, v in product_update.dict().items() if v is not None}
    if "price" in update_data:
        update_data["price"] = float(update_data["price"])
        
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await app.mongodb.products.update_one(
            {"_id": str_to_oid(product_id)},
            {"$set": update_data}
        )

    updated_product = await app.mongodb.products.find_one({"_id": str_to_oid(product_id)})
    updated_product["id"] = str(updated_product["_id"])
    return SuccessResponse(data=ProductResponse(**updated_product), message="Product updated successfully")

@app.delete("/products/{product_id}", response_model=SuccessResponse[dict])
async def delete_product(product_id: str, user: dict = Depends(get_current_user)):
    product = await app.mongodb.products.find_one({"_id": str_to_oid(product_id)})
    if not product:
        raise NotFoundException("Product not found")
    
    if product["vendor_id"] != user["sub"]:
        raise UnauthorizedException("Not authorized to delete this product")

    await app.mongodb.products.update_one(
        {"_id": str_to_oid(product_id)},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    return SuccessResponse(data={"id": product_id}, message="Product deleted successfully")

# Categories
@app.get("/categories", response_model=SuccessResponse[List[CategoryResponse]])
async def list_categories():
    cursor = app.mongodb.categories.find({})
    categories = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        categories.append(CategoryResponse(**doc))
    return SuccessResponse(data=categories)

@app.post("/categories", response_model=SuccessResponse[CategoryResponse])
async def create_category(category: CategoryCreate, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin": # Assuming 'admin' role, or maybe we allow vendors? Instructions say "admin only". 
        # Since auth service currently only has user/vendor, we might need to assume a hardcoded admin or check specific ID. 
        # For now, I will enforce 'admin' role check. If no user has 'admin' role, this endpoint is effectively locked, which is safe.
        # Alternatively, checking for 'vendor' might be what the user meant if they forgot to add 'admin' enum, but I will stick to instructions.
        raise UnauthorizedException("Only admins can create categories")

    existing = await app.mongodb.categories.find_one({"slug": category.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Category slug already exists")

    cat_db = CategoryDB(**category.dict())
    new_cat = await app.mongodb.categories.insert_one(cat_db.dict(by_alias=True, exclude={"id"}))
    created_cat = await app.mongodb.categories.find_one({"_id": new_cat.inserted_id})
    created_cat["id"] = str(created_cat["_id"])

    return SuccessResponse(data=CategoryResponse(**created_cat), message="Category created successfully")
