# app/schemas/rate.py

from pydantic import BaseModel
from datetime import date


class CommodityRate(BaseModel):
    commodity_id: int
    name: str
    unit: str
    price: float | None  # None if no rate exists yet for this commodity


class CategoryRates(BaseModel):
    category_id: int
    category_name: str
    commodities: list[CommodityRate]


class RatesResponse(BaseModel):
    effective_date: str
    categories: list[CategoryRates]