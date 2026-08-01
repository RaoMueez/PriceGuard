# app/api/routers/markets.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Market
from app.schemas.market import MarketResponse

router = APIRouter(prefix="/api/markets", tags=["Markets"])


@router.get("", response_model=list[MarketResponse])
def get_markets(db: Session = Depends(get_db)):
    return db.query(Market).all()