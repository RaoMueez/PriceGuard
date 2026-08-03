# app/api/routers/complaints.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Complaint, Commodity, Market, User
from app.schemas.complaint import ComplaintCreate, ComplaintResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/complaints", tags=["Complaints"])


@router.post("", response_model=ComplaintResponse, status_code=201)
def submit_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before submitting complaints.")

    commodity = db.query(Commodity).filter(Commodity.id == payload.commodity_id).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found.")

    market = db.query(Market).filter(Market.id == payload.market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found.")

    new_complaint = Complaint(
        user_id=current_user.id,
        commodity_id=payload.commodity_id,
        market_id=payload.market_id,
        shop_name=payload.shop_name,
        reported_price=payload.reported_price,
        receipt_image_url=payload.receipt_image_url,
    )
    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)

    return new_complaint


@router.get("/my-complaints", response_model=list[ComplaintResponse])
def get_my_complaints(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Complaint).filter(Complaint.user_id == current_user.id).order_by(Complaint.created_at.desc()).all()