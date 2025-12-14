from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from shared.security_config import sanitize_input

class CartItemAdd(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., gt=0)

class CartItemResponse(BaseModel):
    product_id: str
    quantity: int
    price: Decimal
    name: Optional[str] = None # Added for easier UI display if we store it or fetch it

class CartResponse(BaseModel):
    user_id: str
    items: List[CartItemResponse]
    updated_at: datetime
    total: Decimal

class OrderCreate(BaseModel):
    shipping_address: Optional[str] = None
    
    @field_validator('shipping_address')
    def sanitize_address(cls, v):
        return sanitize_input(v)

class OrderStatusUpdate(BaseModel):
    status: str
    payment_id: Optional[str] = None

    @field_validator('status')
    def sanitize_status(cls, v):
        return sanitize_input(v)


class OrderResponse(BaseModel):
    id: str
    user_id: str
    items: List[OrderItemResponse]
    total_amount: Decimal
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
