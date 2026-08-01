# app/api/routers/rates.py

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Category, Commodity, OfficialRate
from app.schemas.rate import RatesResponse, CategoryRates, CommodityRate

router = APIRouter(prefix="/api/rates", tags=["Rates"])


@router.get("", response_model=RatesResponse)
def get_official_rates(
    effective_date: date_type = Query(default=None, description="Defaults to the latest available date"),
    db: Session = Depends(get_db),
):
    # If no date given, use the most recent effective_date that has any rate data
    if effective_date is None:
        latest = db.query(OfficialRate.effective_date).order_by(OfficialRate.effective_date.desc()).first()
        effective_date = latest[0] if latest else date_type.today()

    categories = db.query(Category).all()
    result_categories = []

    for category in categories:
        commodities = db.query(Commodity).filter(
            Commodity.category_id == category.id,
            Commodity.is_active == True
        ).all()

        commodity_rates = []
        for commodity in commodities:
            rate = db.query(OfficialRate).filter(
                OfficialRate.commodity_id == commodity.id,
                OfficialRate.effective_date == effective_date
            ).first()

            commodity_rates.append(CommodityRate(
                commodity_id=commodity.id,
                name=commodity.name,
                unit=commodity.unit,
                price=rate.price if rate else None
            ))

        result_categories.append(CategoryRates(
            category_id=category.id,
            category_name=category.name,
            commodities=commodity_rates
        ))

    return RatesResponse(
        effective_date=str(effective_date),
        categories=result_categories
    )