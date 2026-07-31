# app/api/routers/admin.py

import io
from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Commodity, OfficialRate, User
from app.schemas.admin import RateUploadResult
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

    required_columns = {"Item Name", "Unit", "Price"}
    if not required_columns.issubset(set(df.columns)):
        raise HTTPException(
            status_code=400,
            detail=f"File must contain columns: {required_columns}. Found: {list(df.columns)}"
        )

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