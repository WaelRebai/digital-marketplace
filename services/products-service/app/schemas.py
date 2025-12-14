from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from shared.security_config import sanitize_input

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    slug: str = Field(..., min_length=1)

    @field_validator('name', 'description', 'slug')
    def sanitize_fields(cls, v):
        return sanitize_input(v)

class CategoryResponse(CategoryCreate):
    id: str

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str
    price: Decimal = Field(..., gt=0)
    category: str
    image_url: Optional[str] = None
    stock: int = Field(0, ge=0)

    @field_validator('name', 'description', 'category', 'image_url')
    def sanitize_fields(cls, v):
        return sanitize_input(v)

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0)
    category: Optional[str] = None
    image_url: Optional[str] = None
    stock: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class ProductResponse(ProductCreate):
    id: str
    vendor_id: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    total: int
    page: int
    limit: int
