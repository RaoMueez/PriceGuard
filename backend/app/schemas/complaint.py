# app/schemas/complaint.py

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.models.models import ComplaintStatus


class ComplaintCreate(BaseModel):
    commodity_id: int
    market_id: int
    reported_price: float
    receipt_image_url: str


class ComplaintResponse(BaseModel):
    id: UUID
    user_id: UUID
    commodity_id: int
    market_id: int
    reported_price: float
    receipt_image_url: str
    status: ComplaintStatus
    created_at: datetime

    class Config:
        from_attributes = True