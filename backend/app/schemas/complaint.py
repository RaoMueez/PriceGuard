# app/schemas/complaint.py

from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.models.models import ComplaintStatus


class ComplaintResponse(BaseModel):
    id: UUID
    user_id: UUID
    commodity_id: int
    market_id: int
    shop_name: str | None
    reported_price: float
    official_price_at_submission: float | None
    receipt_image_url: str
    ai_extracted_price: float | None
    device_latitude: float | None
    device_longitude: float | None
    distance_from_market_km: float | None
    flags: str | None
    status: ComplaintStatus
    created_at: datetime

    class Config:
        from_attributes = True