from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(..., pattern="^(user|vendor)$")
    full_name: str
    phone: Optional[str] = None
    address: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class ProfileResponse(BaseModel):
    user_id: str
    full_name: str
    phone: Optional[str]
    address: Optional[str]

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    created_at: datetime
    profile: Optional[ProfileResponse] = None
