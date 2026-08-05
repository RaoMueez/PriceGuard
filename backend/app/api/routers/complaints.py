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

# Absurd/spam price ceiling: reports at or above this multiple of the
# official price are treated as troll/spam entries rather than genuine
# overpricing complaints, and are auto-rejected before any OCR is run.
ABSURD_PRICE_MULTIPLIER = 2.0


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


def _save_complaint(
    db: Session,
    current_user: User,
    commodity_id: int,
    market_id: int,
    shop_name: str,
    reported_price: float,
    official_price: float | None,
    image_bytes: bytes,
    device_latitude: float | None,
    device_longitude: float | None,
    distance_km: float | None,
    triggered_flags: list[str],
    final_status: ComplaintStatus,
    ai_extracted_price: float | None = None,
) -> Complaint:
    """Shared save path so every exit point (early rejects and the full-pipeline
    end) writes the record the exact same way."""
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
    final_status = ComplaintStatus.pending  # default if nothing flags/rejects it

    # Official price is needed for both the Step 4 math check and the audit
    # snapshot on every save path (including early rejects), so fetch once up front.
    official_price = _get_latest_official_price(db, commodity_id)

    # ============================================================
    # STEP 1 — GPS / HAVERSINE DISTANCE CHECK (reject on mismatch)
    # ============================================================
    distance_km = None
    if device_latitude is not None and device_longitude is not None:
        distance_km = haversine_distance_km(
            device_latitude, device_longitude, market.latitude, market.longitude
        )

        if distance_km > MAX_ALLOWED_DISTANCE_KM:
            triggered_flags.append(f"location_mismatch: {round(distance_km, 2)}km from market")
            final_status = ComplaintStatus.suspicious_location_mismatch

            return _save_complaint(
                db, current_user, commodity_id, market_id, shop_name,
                reported_price, official_price, image_bytes,
                device_latitude, device_longitude, distance_km,
                triggered_flags, final_status,
            )
    else:
        # Missing location doesn't block submission — just noted for admin visibility.
        triggered_flags.append("location_not_provided")

    # ============================================================
    # STEP 2 — VELOCITY TRACKING (flag only, does not block here;
    # applied as the highest-severity override at the very end)
    # ============================================================
    is_coordinated_attack = False
    if shop_name and shop_name.strip():
        recent_count = check_shop_velocity(db, shop_name)
        if recent_count >= VELOCITY_THRESHOLD:
            is_coordinated_attack = True
            triggered_flags.append(f"velocity_alert: {recent_count} reports on this shop in 24h")

    # ============================================================
    # STEP 3 — FAKE IMAGE FILTER (OpenCV, reject if invalid)
    # ============================================================
    authenticity = compute_receipt_authenticity(image_bytes)

    if not authenticity["is_likely_valid_receipt"]:
        triggered_flags.append(f"invalid_image:{authenticity['reason']}")
        final_status = ComplaintStatus.auto_rejected_invalid_image

        return _save_complaint(
            db, current_user, commodity_id, market_id, shop_name,
            reported_price, official_price, image_bytes,
            device_latitude, device_longitude, distance_km,
            triggered_flags, final_status,
        )

    # ============================================================
    # STEP 4 — MATH FILTER (reject if underpriced OR absurdly overpriced)
    # ============================================================
    if official_price is not None and reported_price <= official_price:
        triggered_flags.append("no_overpricing_detected")
        final_status = ComplaintStatus.auto_rejected_no_overpricing

        return _save_complaint(
            db, current_user, commodity_id, market_id, shop_name,
            reported_price, official_price, image_bytes,
            device_latitude, device_longitude, distance_km,
            triggered_flags, final_status,
        )

    # Absurd Price / Spam check — e.g. reporting 5000 PKR for a 120 PKR onion.
    # Runs immediately after the underpricing check, still before any OCR,
    # since a report this far outside plausible range doesn't need the
    # expense of tampering verification to be treated as spam.
    if official_price is not None and reported_price >= official_price * ABSURD_PRICE_MULTIPLIER:
        triggered_flags.append(
            f"absurd_price: reported={reported_price} is >= {ABSURD_PRICE_MULTIPLIER}x official={official_price}"
        )
        final_status = ComplaintStatus.suspicious_absurd_price_spam

        return _save_complaint(
            db, current_user, commodity_id, market_id, shop_name,
            reported_price, official_price, image_bytes,
            device_latitude, device_longitude, distance_km,
            triggered_flags, final_status,
        )

    # ============================================================
    # STEP 5 — OCR EXTRACTION & TAMPERING CHECK / HANDWRITTEN FALLBACK
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
        # Tampering check — does OCR price match what the user reported?
        if abs(ai_extracted_price - reported_price) > PRICE_MATCH_TOLERANCE_RS:
            triggered_flags.append(
                f"price_mismatch: reported={reported_price}, ocr_extracted={ai_extracted_price}"
            )
            final_status = ComplaintStatus.suspicious_price_mismatch
    else:
        # OCR found nothing, but the image passed Step 3's "has real content" check —
        # most likely a handwritten receipt that needs a human to verify.
        triggered_flags.append("no_ocr_price_extracted_likely_handwritten")
        final_status = ComplaintStatus.pending_manual_review_handwritten

    # Velocity is the highest-severity signal — overrides whatever Step 5 landed on,
    # but the Step 5 flag stays in `flags` for full admin transparency.
    if is_coordinated_attack:
        final_status = ComplaintStatus.potential_coordinated_attack

    # ============================================================
    # SAVE FINAL RECORD
    # ============================================================
    return _save_complaint(
        db, current_user, commodity_id, market_id, shop_name,
        reported_price, official_price, image_bytes,
        device_latitude, device_longitude, distance_km,
        triggered_flags, final_status,
        ai_extracted_price=ai_extracted_price,
    )


@router.get("/my-complaints", response_model=list[ComplaintResponse])
def get_my_complaints(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Complaint).filter(Complaint.user_id == current_user.id).order_by(Complaint.created_at.desc()).all()