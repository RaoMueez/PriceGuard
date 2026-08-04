# app/api/routers/complaints.py

import os
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Complaint, Commodity, Market, User, OfficialRate, ComplaintStatus
from app.schemas.complaint import ComplaintResponse
from app.api.deps import get_current_user
from app.services.ocr_service import process_receipt, process_handwritten_receipt
from app.services.image_validation_service import compute_receipt_authenticity
from app.services.security_service import haversine_distance_km, check_shop_velocity, MAX_ALLOWED_DISTANCE_KM, VELOCITY_THRESHOLD

router = APIRouter(prefix="/api/complaints", tags=["Complaints"])

UPLOAD_DIR = "app/uploads/receipts"

# Tolerance for considering OCR-extracted price "matching" the reported price
# (accounts for minor OCR digit misreads, e.g., 150 vs 156)
PRICE_MATCH_TOLERANCE_RS = 5.0


def _get_latest_official_price(db: Session, commodity_id: int) -> float | None:
    latest_rate = (
        db.query(OfficialRate)
        .filter(OfficialRate.commodity_id == commodity_id)
        .order_by(OfficialRate.effective_date.desc())
        .first()
    )
    return latest_rate.price if latest_rate else None


def _save_receipt_image(image_bytes: bytes) -> str:
    """Saves the receipt image to local disk and returns its relative URL path."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(image_bytes)

    return f"/uploads/receipts/{filename}"


@router.post("", response_model=ComplaintResponse, status_code=201)
async def submit_complaint(
    file: UploadFile = File(...),
    commodity_id: int = Form(...),
    market_id: int = Form(...),
    shop_name: str = Form(default=""),
    reported_price: float = Form(...),
    device_latitude: float | None = Form(default=None),
    device_longitude: float | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before submitting complaints.")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    commodity = db.query(Commodity).filter(Commodity.id == commodity_id).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found.")

    market = db.query(Market).filter(Market.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found.")

    image_bytes = await file.read()

    # Collected throughout the checks below — shown to admins for full transparency
    triggered_flags: list[str] = []
    ai_extracted_price: float | None = None
    final_status = ComplaintStatus.pending  # default if nothing flags it

    # ============================================================
    # RULE 1 — MATH FILTER (cheapest check, run first)
    # ============================================================
    official_price = _get_latest_official_price(db, commodity_id)

    if official_price is not None and reported_price <= official_price:
        final_status = ComplaintStatus.auto_rejected_no_overpricing
        triggered_flags.append("no_overpricing_detected")

        # Still save the image for audit purposes, but skip the remaining
        # (more expensive) checks since this complaint is already rejected.
        image_url = _save_receipt_image(image_bytes)

        new_complaint = Complaint(
            user_id=current_user.id,
            commodity_id=commodity_id,
            market_id=market_id,
            shop_name=shop_name or None,
            reported_price=reported_price,
            official_price_at_submission=official_price,
            receipt_image_url=image_url,
            device_latitude=device_latitude,
            device_longitude=device_longitude,
            flags=",".join(triggered_flags),
            status=final_status,
        )
        db.add(new_complaint)
        db.commit()
        db.refresh(new_complaint)
        return new_complaint

    # ============================================================
    # RULE 2 — FAKE IMAGE FILTER (OpenCV)
    # ============================================================
    authenticity = compute_receipt_authenticity(image_bytes)

    if not authenticity["is_likely_valid_receipt"]:
        final_status = ComplaintStatus.auto_rejected_invalid_image
        triggered_flags.append(f"invalid_image:{authenticity['reason']}")

        image_url = _save_receipt_image(image_bytes)

        new_complaint = Complaint(
            user_id=current_user.id,
            commodity_id=commodity_id,
            market_id=market_id,
            shop_name=shop_name or None,
            reported_price=reported_price,
            official_price_at_submission=official_price,
            receipt_image_url=image_url,
            device_latitude=device_latitude,
            device_longitude=device_longitude,
            flags=",".join(triggered_flags),
            status=final_status,
        )
        db.add(new_complaint)
        db.commit()
        db.refresh(new_complaint)
        return new_complaint

    # ============================================================
    # RULE 3 & 4 — OCR-BASED TAMPERING CHECK / HANDWRITTEN FALLBACK
    # ============================================================
    commodity_name = commodity.name
    ocr_found_price = False

    try:
        printed_result = process_receipt(image_bytes, [commodity_name])
        printed_item = printed_result.get("extracted_items", {}).get(commodity_name, {})
        if printed_item.get("price") is not None:
            ai_extracted_price = printed_item["price"]
            ocr_found_price = True
    except Exception:
        pass

    if not ocr_found_price:
        try:
            handwritten_result = process_handwritten_receipt(image_bytes, [commodity_name])
            hw_item = handwritten_result.get("extracted_items", {}).get(commodity_name, {})
            if hw_item.get("price") is not None:
                ai_extracted_price = hw_item["price"]
                ocr_found_price = True
        except Exception:
            pass

    if ocr_found_price:
        # RULE 3: Tampering check — does OCR price match what the user reported?
        if abs(ai_extracted_price - reported_price) > PRICE_MATCH_TOLERANCE_RS:
            final_status = ComplaintStatus.suspicious_price_mismatch
            triggered_flags.append(
                f"price_mismatch: reported={reported_price}, ocr_extracted={ai_extracted_price}"
            )
    else:
        # RULE 4: OCR found nothing, but the image passed the "has real content" check
        # from Rule 2 — most likely a handwritten receipt that needs a human to verify.
        final_status = ComplaintStatus.pending_manual_review_handwritten
        triggered_flags.append("no_ocr_price_extracted_likely_handwritten")

    # ============================================================
    # RULE 5 — GPS GEO-FENCING
    # ============================================================
    distance_km = None
    if device_latitude is not None and device_longitude is not None:
        distance_km = haversine_distance_km(
            device_latitude, device_longitude, market.latitude, market.longitude
        )

        if distance_km > MAX_ALLOWED_DISTANCE_KM:
            triggered_flags.append(f"location_mismatch: {round(distance_km, 2)}km from market")
            # Location mismatch takes priority over a "pending" default, but doesn't
            # override an already-set price_mismatch/handwritten flag — both are kept
            # in `flags`, with location treated as the more severe signal for `status`.
            final_status = ComplaintStatus.suspicious_location_mismatch
    else:
        triggered_flags.append("location_not_provided")

    # ============================================================
    # RULE 6 — VELOCITY TRACKING (ANTI-SPAM)
    # ============================================================
    if shop_name and shop_name.strip():
        recent_count = check_shop_velocity(db, shop_name)
        if recent_count >= VELOCITY_THRESHOLD:
            triggered_flags.append(f"velocity_alert: {recent_count} reports on this shop in 24h")
            # Coordinated attack is the highest-severity signal — overrides other suspicious statuses
            final_status = ComplaintStatus.potential_coordinated_attack

    # ============================================================
    # SAVE FINAL RECORD
    # ============================================================
    image_url = _save_receipt_image(image_bytes)

    new_complaint = Complaint(
        user_id=current_user.id,
        commodity_id=commodity_id,
        market_id=market_id,
        shop_name=shop_name or None,
        reported_price=reported_price,
        official_price_at_submission=official_price,
        receipt_image_url=image_url,
        ai_extracted_price=ai_extracted_price,
        device_latitude=device_latitude,
        device_longitude=device_longitude,
        distance_from_market_km=distance_km,
        flags=",".join(triggered_flags) if triggered_flags else None,
        status=final_status,
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