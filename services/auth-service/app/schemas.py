from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from shared.security_config import validate_password_strength, sanitize_input

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field(..., pattern="^(user|vendor|admin)$")
    full_name: str

    @field_validator('password')
    def password_complexity(cls, v):
        if not validate_password_strength(v):
            raise ValueError('Password must be at least 8 characters long and contain uppercase, lowercase, and numbers')
        return v
    
    @field_validator('role')
    def sanitize_role(cls, v):
        return sanitize_input(v)
    phone: Optional[str] = None
    address: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

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
