from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class ProductDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    vendor_id: str
    name: str
    description: str
    price: Decimal
    category: str
    image_url: Optional[str] = None
    stock: int
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True

class CategoryDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    description: Optional[str] = None
    slug: str

    class Config:
        populate_by_name = True
