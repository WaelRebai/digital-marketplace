from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class PaymentDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    order_id: str
    user_id: str
    amount: Decimal
    status: str = "pending" # pending, completed, failed
    transaction_id: str
    payment_method: str
    processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
