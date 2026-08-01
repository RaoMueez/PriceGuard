# app/schemas/market.py

from pydantic import BaseModel


class MarketResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float

    class Config:
        from_attributes = True