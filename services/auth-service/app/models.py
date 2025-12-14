from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class UserDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    email: EmailStr
    password_hash: str
    role: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

class ProfileDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    full_name: str
    phone: Optional[str] = None
    address: Optional[str] = None

    class Config:
        populate_by_name = True
