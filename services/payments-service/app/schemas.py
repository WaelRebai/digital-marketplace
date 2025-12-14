from pydantic import BaseModel, Field, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime
from shared.security_config import sanitize_input

class PaymentMethod(str):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"

class PaymentProcess(BaseModel):
    order_id: str
    payment_method: str = Field(..., pattern="^(credit_card|debit_card|paypal)$")
    card_details: dict # Dummy dict for now

    @field_validator('order_id', 'payment_method')
    def sanitize_fields(cls, v):
        return sanitize_input(v)

class PaymentResponse(BaseModel):
    id: str
    order_id: str
    user_id: str
    amount: Decimal
    status: str
    transaction_id: str
    payment_method: str
    processed_at: Optional[datetime] = None
    created_at: datetime
