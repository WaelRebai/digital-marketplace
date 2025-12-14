from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import timedelta, datetime
import os
import sys

# Add the parent directory to sys.path to resolve shared imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.utils import (
    get_db_client, settings, get_password_hash, verify_password, 
    create_access_token, verify_token, require_auth, 
    SuccessResponse, ErrorResponse, NotFoundException, UnauthorizedException,
    HealthResponse, create_access_token, create_refresh_token, verify_refresh_token,
    verify_password, get_password_hash, require_auth, settings,
    UnauthorizedException, NotFoundException
)
from shared.logging_config import setup_logging, RequestLoggingMiddleware
from shared.security_config import setup_rate_limiting, SecurityHeadersMiddleware, limiter

from app.schemas import UserRegister, UserLogin, Token, UserResponse, ProfileResponse, ProfileUpdate, RefreshTokenRequest
from app.models import UserDB, ProfileDB

# Setup Logging
logger = setup_logging("auth-service")

app = FastAPI(title="Auth Service")

# Security Setup
setup_rate_limiting(app)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware, service_name="auth-service")

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
    app.mongodb = app.mongodb_client.auth_db
    # Create unique index for email
    await app.mongodb.users.create_index("email", unique=True)
    # Create TTL index for revoked tokens
    await app.mongodb.revoked_tokens.create_index("exp", expireAfterSeconds=0)

@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_client.close()

# --- Endpoints ---

@app.post("/register", response_model=SuccessResponse[UserResponse])
async def register(user: UserRegister):
    existing_user = await app.mongodb.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_db = UserDB(
        email=user.email,
        password_hash=get_password_hash(user.password),
        role=user.role
    )
    new_user = await app.mongodb.users.insert_one(user_db.dict(by_alias=True, exclude={"id"}))
    created_user = await app.mongodb.users.find_one({"_id": new_user.inserted_id})
    created_user["id"] = str(created_user["_id"])

    profile_db = ProfileDB(
        user_id=str(new_user.inserted_id),
        full_name=user.full_name,
        phone=user.phone,
        address=user.address
    )
    await app.mongodb.profiles.insert_one(profile_db.dict(by_alias=True, exclude={"id"}))
    
    # Construct response
    profile_resp = ProfileResponse(**profile_db.dict())
    user_resp = UserResponse(**created_user, profile=profile_resp)
    
    return SuccessResponse(data=user_resp, message="User registered successfully")

@app.post("/login", response_model=SuccessResponse[Token])
@limiter.limit("5/minute")
async def login(user_credentials: UserLogin, request: Request):
    user = await app.mongodb.users.find_one({"email": user_credentials.email})
    if not user or not verify_password(user_credentials.password, user["password_hash"]):
        raise UnauthorizedException("Incorrect email or password")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["_id"]), "role": user["role"]},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user["_id"]), "role": user["role"]}
    )
    return SuccessResponse(data=Token(
        access_token=access_token, 
        refresh_token=refresh_token, 
        token_type="bearer"
    ))

@app.get("/verify", response_model=SuccessResponse[dict])
async def verify(payload: dict = Depends(require_auth)):
    # Check Blacklist
    if "jti" in payload:
         is_revoked = await app.mongodb.revoked_tokens.find_one({"jti": payload["jti"]})
         if is_revoked:
             raise UnauthorizedException("Token has been revoked")
    return SuccessResponse(data=payload, message="Token is valid")

@app.post("/refresh", response_model=SuccessResponse[Token])
async def refresh_token(request: RefreshTokenRequest):
    payload = verify_refresh_token(request.refresh_token)
    # Check Blacklist
    if "jti" in payload:
         is_revoked = await app.mongodb.revoked_tokens.find_one({"jti": payload["jti"]})
         if is_revoked:
             raise UnauthorizedException("Refresh token has been revoked")
    
    # Issue new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": payload["sub"], "role": payload["role"]},
        expires_delta=access_token_expires
    )
    # Return original refresh? Or rotate? Simple: return original or just access. 
    # Schema `Token` validation requires `refresh_token`. So either return old or new.
    # I'll return the incoming refresh token for simplicity, or create new.
    # Let's rotate for better security.
    new_refresh_token = create_refresh_token(
        data={"sub": payload["sub"], "role": payload["role"]}
    )
    
    # Revoke old refresh token? If rotation enabled.
    # For now, let's strictly follow "Implement refresh tokens".
    # I'll return new pair.
    
    return SuccessResponse(data=Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    ))

@app.post("/logout", response_model=SuccessResponse[dict])
async def logout(request: RefreshTokenRequest, payload: dict = Depends(require_auth)):
    # Revoke Access Token
    if "jti" in payload:
        await app.mongodb.revoked_tokens.insert_one({
            "jti": payload["jti"],
            "exp": datetime.fromtimestamp(payload["exp"])
        })
    
    # Revoke Refresh Token
    refresh_payload = verify_refresh_token(request.refresh_token)
    if "jti" in refresh_payload:
         await app.mongodb.revoked_tokens.insert_one({
            "jti": refresh_payload["jti"],
            "exp": datetime.fromtimestamp(refresh_payload["exp"])
        })
        
    return SuccessResponse(message="Logged out successfully")

@app.get("/users/{user_id}", response_model=SuccessResponse[UserResponse])
async def get_user_profile(user_id: str, payload: dict = Depends(require_auth)):
    # Verify authorization (allow admin or self)
    if payload.get("sub") != user_id and payload.get("role") != "admin": # Assuming admin role exists or future proofing
         raise UnauthorizedException("Not authorized to view this profile")

    user = await app.mongodb.users.find_one({"_id": user_id}) # Note: _id is ObjectId? Wait, insert_one returns ObjectId usually, need to handle that or use str id in DB.
    # Actually motor returns _id as ObjectId. I should convert.
    # For simplicity, assuming helper or just string conversion.
    # Let's fix ObjectId handling. The shared utils didn't enforce str id.
    # Pydantic models use alias="_id", but string type. 
    # Let's try to query with ObjectId if simple str fails, but standard mongo expects ObjectId.
    # For this task, I will assume str(ObjectId) works if I implement a PydanticObjectId helper, but I don't have that in shared. 
    # I will stick to string conversion.
    
    from bson import ObjectId
    try:
        oid = ObjectId(user_id)
    except:
        raise NotFoundException("Invalid User ID format")

    user = await app.mongodb.users.find_one({"_id": oid})
    if not user:
        raise NotFoundException("User not found")

    profile = await app.mongodb.profiles.find_one({"user_id": user_id})
    
    user["id"] = str(user["_id"])
    profile_resp = None
    if profile:
        profile_resp = ProfileResponse(**profile)
    
    return SuccessResponse(data=UserResponse(**user, profile=profile_resp))

@app.put("/users/{user_id}", response_model=SuccessResponse[ProfileResponse])
async def update_user_profile(user_id: str, profile_update: ProfileUpdate, payload: dict = Depends(require_auth)):
    if payload.get("sub") != user_id:
         raise UnauthorizedException("Not authorized to update this profile")

    update_data = {k: v for k, v in profile_update.dict().items() if v is not None}
    
    if update_data:
        await app.mongodb.profiles.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
    
    updated_profile = await app.mongodb.profiles.find_one({"user_id": user_id})
    if not updated_profile:
         raise NotFoundException("Profile not found")

    return SuccessResponse(data=ProfileResponse(**updated_profile), message="Profile updated successfully")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "unhealthy"
    try:
        await app.mongodb_client.admin.command('ping')
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    status_code = "healthy" if db_status == "connected" else "unhealthy"
    
    if status_code == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service Unhealthy"
        )

    return HealthResponse(
        service="auth-service",
        status=status_code,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        database=db_status
    )
