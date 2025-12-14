from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field

class CartItemDB(BaseModel):
    product_id: str
    quantity: int
    price: Decimal # Snapshot
    name: Optional[str] = None

class CartDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    items: List[CartItemDB] = []
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

class OrderItemDB(BaseModel):
    product_id: str
    quantity: int
    price: Decimal

class OrderDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    items: List[OrderItemDB]
    total_amount: Decimal
    status: str = "pending" # pending, completed, cancelled
    payment_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
