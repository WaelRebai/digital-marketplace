from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import timedelta
import os
import sys

# Add the parent directory to sys.path to resolve shared imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.utils import (
    get_db_client, settings, get_password_hash, verify_password, 
    create_access_token, verify_token, require_auth, 
    SuccessResponse, ErrorResponse, NotFoundException, UnauthorizedException
)
from app.schemas import UserRegister, UserLogin, Token, UserResponse, ProfileResponse, ProfileUpdate
from app.models import UserDB, ProfileDB

app = FastAPI(title="Auth Service")

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
    new_user = await app.mongodb.users.insert_one(user_db.dict(by_alias=True))
    created_user = await app.mongodb.users.find_one({"_id": new_user.inserted_id})
    created_user["id"] = str(created_user["_id"])

    profile_db = ProfileDB(
        user_id=str(new_user.inserted_id),
        full_name=user.full_name,
        phone=user.phone,
        address=user.address
    )
    await app.mongodb.profiles.insert_one(profile_db.dict(by_alias=True))
    
    # Construct response
    profile_resp = ProfileResponse(**profile_db.dict())
    user_resp = UserResponse(**created_user, profile=profile_resp)
    
    return SuccessResponse(data=user_resp, message="User registered successfully")

@app.post("/login", response_model=SuccessResponse[Token])
async def login(user_credentials: UserLogin):
    user = await app.mongodb.users.find_one({"email": user_credentials.email})
    if not user or not verify_password(user_credentials.password, user["password_hash"]):
        raise UnauthorizedException("Incorrect email or password")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["_id"]), "role": user["role"]},
        expires_delta=access_token_expires
    )
    return SuccessResponse(data=Token(access_token=access_token, token_type="bearer"))

@app.get("/verify", response_model=SuccessResponse[dict])
async def verify(payload: dict = Depends(require_auth)):
    return SuccessResponse(data=payload, message="Token is valid")

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
