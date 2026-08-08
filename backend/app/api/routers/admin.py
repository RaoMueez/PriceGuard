# app/api/routers/admin.py

import io
from datetime import date, datetime
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.models import Commodity, OfficialRate, User, Complaint, Market
from app.schemas.admin import RateUploadResult
from app.schemas.complaint import ComplaintAdminResponse, ComplaintStatusUpdate
from app.api.deps import get_admin_user

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/upload-rates", response_model=RateUploadResult)
def upload_official_rates(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    filename = file.filename.lower()
    if not (filename.endswith(".csv") or filename.endswith(".xlsx") or filename.endswith(".xls")):
        raise HTTPException(status_code=400, detail="Only CSV or Excel files are supported.")

    contents = file.file.read()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Normalize column headers: strip whitespace, lowercase for matching
    df.columns = [str(col).strip() for col in df.columns]
    column_map = {col.lower(): col for col in df.columns}

    required_columns_lower = {"item name", "unit", "price"}
    if not required_columns_lower.issubset(set(column_map.keys())):
        raise HTTPException(
            status_code=400,
            detail=f"File must contain columns: Item Name, Unit, Price. Found: {list(df.columns)}"
        )

    # Rename columns to standard names for consistent access below
    df = df.rename(columns={
        column_map["item name"]: "Item Name",
        column_map["unit"]: "Unit",
        column_map["price"]: "Price",
    })

    # Also strip whitespace from item name values themselves
    df["Item Name"] = df["Item Name"].astype(str).str.strip()

    today = date.today()
    rates_inserted = 0
    skipped_items = []

    for _, row in df.iterrows():
        item_name = str(row["Item Name"]).strip()
        price = row["Price"]

        try:
            price = float(price)
            if price <= 0:
                raise ValueError
        except (ValueError, TypeError):
            skipped_items.append(f"{item_name} (invalid price)")
            continue

        commodity = db.query(Commodity).filter(Commodity.name.ilike(item_name)).first()
        if not commodity:
            skipped_items.append(f"{item_name} (no matching commodity)")
            continue

        # One rate per commodity per day, city-wide — no market dependency
        existing_rate = db.query(OfficialRate).filter(
            OfficialRate.commodity_id == commodity.id,
            OfficialRate.effective_date == today
        ).first()

        if existing_rate:
            existing_rate.price = price
        else:
            new_rate = OfficialRate(
                commodity_id=commodity.id,
                price=price,
                effective_date=today,
                uploaded_by=admin_user.id,
            )
            db.add(new_rate)

        rates_inserted += 1

    db.commit()

    return RateUploadResult(
        total_rows_processed=len(df),
        rates_inserted=rates_inserted,
        skipped_items=skipped_items,
        effective_date=str(today),
    )


def _complaint_to_admin_dict(c: Complaint) -> dict:
    """Shared serializer so the list and update endpoints stay in sync."""
    return {
        "id": c.id,
        "user_id": c.user_id,
        "user_email": c.user.email,
        "commodity_id": c.commodity_id,
        "commodity_name": c.commodity.name,
        "market_id": c.market_id,
        "market_name": c.market.name,
        "market_latitude": c.market.latitude,
        "market_longitude": c.market.longitude,
        "shop_name": c.shop_name,
        "reported_price": c.reported_price,
        "official_price_at_submission": c.official_price_at_submission,
        "receipt_image_url": c.receipt_image_url,
        "ai_extracted_price": c.ai_extracted_price,
        "device_latitude": c.device_latitude,
        "device_longitude": c.device_longitude,
        "distance_from_market_km": c.distance_from_market_km,
        "flags": c.flags,
        "status": c.status,
        "created_at": c.created_at,
        "reviewed_at": c.reviewed_at,
    }


@router.get("/complaints", response_model=list[ComplaintAdminResponse])
def list_complaints(
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Returns all complaints with commodity/market/user info joined in,
    newest first. Filtering (by status, item, date) is done client-side
    in the Streamlit dashboard — dataset size for an FYP demo doesn't
    warrant server-side pagination/filtering yet.
    """
    complaints = (
        db.query(Complaint)
        .options(
            joinedload(Complaint.commodity),
            joinedload(Complaint.market),
            joinedload(Complaint.user),
        )
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return [_complaint_to_admin_dict(c) for c in complaints]


@router.patch("/complaints/{complaint_id}", response_model=ComplaintAdminResponse)
def update_complaint_status(
    complaint_id: UUID,
    payload: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """
    Admin manually overrides a complaint's status (e.g. after reviewing the
    receipt image side-by-side with the reported/OCR prices). Sets
    reviewed_at and appends an audit-trail note to `flags`.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found.")

    if payload.admin_note:
        existing_flags = complaint.flags.split(",") if complaint.flags else []
        existing_flags.append(f"admin_action[{admin_user.email}]: {payload.admin_note}")
        complaint.flags = ",".join(existing_flags)

    complaint.status = payload.status
    complaint.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)

    return _complaint_to_admin_dict(complaint)