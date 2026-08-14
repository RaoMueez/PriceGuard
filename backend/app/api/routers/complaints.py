# app/api/routers/complaints.py

import os
import uuid
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from PIL import Image

from app.db.session import get_db
from app.models.models import Complaint, Commodity, Market, User, OfficialRate, ComplaintStatus
from app.schemas.complaint import ComplaintResponse, MyComplaintResponse
from app.api.deps import get_current_user
from app.services.ocr_service import process_receipt, process_handwritten_receipt
from app.services.image_validation_service import compute_receipt_authenticity
from app.services.security_service import haversine_distance_km, check_shop_velocity, MAX_ALLOWED_DISTANCE_KM, VELOCITY_THRESHOLD

router = APIRouter(prefix="/api/complaints", tags=["Complaints"])

UPLOAD_DIR = "app/uploads/receipts"

PRICE_MATCH_TOLERANCE_RS = 5.0
ABSURD_PRICE_MULTIPLIER = 2.0
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Smallest sane quantity a citizen could plausibly report (10 grams /
# roughly 1 piece) — guards against division-by-near-zero producing an
# absurd effective price from a typo like "0.001" instead of "0.1".
MIN_QUANTITY = 0.01

VALID_COMPLAINT_TYPES = {"overpricing", "short_weight"}

# Longest side, in pixels, that a receipt image is downscaled to before any
# processing. Phone camera photos are often 3000-4000px+ per side — every
# OpenCV step (grayscale, threshold, dilate, Canny) allocates a full-size
# array at that resolution, and combined with TensorFlow/Keras already
# resident in memory for the forecast model, this was pushing Render's
# free-tier 512MB limit and causing silent OOM restarts mid-request.
# 1600px is plenty for OCR — Tesseract doesn't need 12-megapixel input.
MAX_IMAGE_DIMENSION = 1600


def _downscale_image_if_needed(image_bytes: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        if max(width, height) <= MAX_IMAGE_DIMENSION:
            return image_bytes
        scale = MAX_IMAGE_DIMENSION / max(width, height)
        new_size = (int(width * scale), int(height * scale))
        img = img.convert("RGB").resize(new_size, Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()
    except Exception:
        # If anything goes wrong here, don't block the whole submission over
        # it — fall back to the original bytes and let downstream steps
        # (the file-size check, OpenCV, OCR) handle whatever comes through.
        return image_bytes


def _get_latest_official_price(db: Session, commodity_id: int) -> float | None:
    latest_rate = (
        db.query(OfficialRate)
        .filter(OfficialRate.commodity_id == commodity_id)
        .order_by(OfficialRate.effective_date.desc())
        .first()
    )
    return latest_rate.price if latest_rate else None


def _normalize_effective_price(amount_paid: float, quantity: float) -> float:
    """
    Step 0 — turns "I paid X for Y quantity" (either scenario: bought a
    fraction, or received short weight for a fixed payment) into a single
    per-unit effective price, using the same formula for both cases:
    effective_price = amount_paid / quantity.

    This is the ONLY new logic — everything downstream (GPS, velocity,
    OpenCV, Math Filter, absurd-price, OCR tampering) is completely
    unchanged and operates on the resulting reported_price exactly as
    it always has.
    """
    if quantity is None or quantity < MIN_QUANTITY:
        raise HTTPException(
            status_code=400,
            detail=f"Quantity must be at least {MIN_QUANTITY} — please check what you entered."
        )
    if amount_paid is None or amount_paid <= 0:
        raise HTTPException(status_code=400, detail="Amount paid must be a positive number.")

    return round(amount_paid / quantity, 2)

def is_underpriced_or_equal(reported_price: float, official_price: float | None) -> bool:
    """True if there's no violation at all — reported price isn't above official."""
    if official_price is None:
        return False
    return reported_price <= official_price


def is_absurd_price(reported_price: float, official_price: float | None, multiplier: float) -> bool:
    """True if reported price is implausibly high relative to official (likely spam)."""
    if official_price is None:
        return False
    return reported_price >= official_price * multiplier

def _save_receipt_image(image_bytes: bytes) -> str:
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
    complaint_type: str,
    amount_paid: float,
    quantity_stated: float,
    ai_extracted_price: float | None = None,
) -> Complaint:
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
        complaint_type=complaint_type,
        amount_paid=amount_paid,
        quantity_stated=quantity_stated,
    )
    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)
    return new_complaint


@router.post("", response_model=ComplaintResponse, status_code=201)
def submit_complaint(
    file: UploadFile = File(...),
    commodity_id: int = Form(...),
    market_id: int = Form(...),
    shop_name: str = Form(default=""),
    complaint_type: str = Form(...),      # "overpricing" | "short_weight"
    amount_paid: float = Form(...),       # what the citizen actually paid, in Rs.
    quantity: float = Form(...),          # bought (overpricing) or received (short_weight), in the commodity's official unit
    device_latitude: float | None = Form(default=None),
    device_longitude: float | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before submitting complaints.")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    if complaint_type not in VALID_COMPLAINT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"complaint_type must be one of: {', '.join(VALID_COMPLAINT_TYPES)}"
        )

    commodity = db.query(Commodity).filter(Commodity.id == commodity_id).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found.")

    market = db.query(Market).filter(Market.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found.")

    image_bytes = file.file.read()

    # Downscale BEFORE the size check — a legitimately large phone photo
    # (e.g. 7MB) gets shrunk first and likely passes on its processed size,
    # rather than being rejected outright before we even tried to help it.
    # This is also the main memory-pressure fix: every downstream step
    # (OpenCV validation, OCR) now operates on a much smaller array.
    image_bytes = _downscale_image_if_needed(image_bytes)

    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Receipt image is too large ({len(image_bytes) / (1024*1024):.1f} MB). Maximum allowed is 5 MB."
    )

    # ============================================================
    # STEP 0 — NORMALIZE TO PER-UNIT EFFECTIVE PRICE (NEW)
    # Both "bought a fraction" and "got short-weighed" reduce to the same
    # formula here — reported_price from this point on is exactly what
    # every downstream step has always expected: a per-unit price.
    # ============================================================
    reported_price = _normalize_effective_price(amount_paid, quantity)

    triggered_flags: list[str] = [
        f"complaint_type: {complaint_type}",
        f"normalized: Rs.{amount_paid} / {quantity} = Rs.{reported_price} per {commodity.unit}",
    ]
    ai_extracted_price: float | None = None
    final_status = ComplaintStatus.pending

    official_price = _get_latest_official_price(db, commodity_id)

    def _save(status_: ComplaintStatus, extra_flags: list[str] = None):
        flags = triggered_flags + (extra_flags or [])
        return _save_complaint(
            db, current_user, commodity_id, market_id, shop_name,
            reported_price, official_price, image_bytes,
            device_latitude, device_longitude, distance_km,
            flags, status_, complaint_type, amount_paid, quantity,
            ai_extracted_price=ai_extracted_price,
        )

    # ============================================================
    # STEP 1 — GPS / HAVERSINE DISTANCE CHECK
    # ============================================================
    distance_km = None
    if device_latitude is not None and device_longitude is not None:
        distance_km = haversine_distance_km(
            device_latitude, device_longitude, market.latitude, market.longitude
        )
        if distance_km > MAX_ALLOWED_DISTANCE_KM:
            return _save(
                ComplaintStatus.suspicious_location_mismatch,
                [f"location_mismatch: {round(distance_km, 2)}km from market"],
            )
    else:
        triggered_flags.append("location_not_provided")

    # ============================================================
    # STEP 2 — VELOCITY TRACKING (flag only)
    # ============================================================
    is_coordinated_attack = False
    if shop_name and shop_name.strip():
        recent_count = check_shop_velocity(db, shop_name)
        if recent_count >= VELOCITY_THRESHOLD:
            is_coordinated_attack = True
            triggered_flags.append(f"velocity_alert: {recent_count} reports on this shop in 24h")

    # ============================================================
    # STEP 3 — FAKE IMAGE FILTER
    # ============================================================
    authenticity = compute_receipt_authenticity(image_bytes)
    if not authenticity["is_likely_valid_receipt"]:
        return _save(
            ComplaintStatus.auto_rejected_invalid_image,
            [f"invalid_image:{authenticity['reason']}"],
        )

    # ============================================================
    # STEP 4 — MATH FILTER (unchanged — operates on the NORMALIZED price)
    # ============================================================
    if is_underpriced_or_equal(reported_price, official_price):
        return _save(
            ComplaintStatus.auto_rejected_no_overpricing,
            ["no_overpricing_detected"],
        )

    if is_absurd_price(reported_price, official_price, ABSURD_PRICE_MULTIPLIER):
        return _save(
            ComplaintStatus.suspicious_absurd_price_spam,
            [f"absurd_price: normalized={reported_price} is >= {ABSURD_PRICE_MULTIPLIER}x official={official_price}"],
        )

    # ============================================================
    # STEP 5 — OCR EXTRACTION & TAMPERING CHECK / HANDWRITTEN FALLBACK
    #
    # IMPORTANT CHANGE: OCR is compared against `amount_paid`, not the
    # normalized `reported_price`. A real receipt shows the actual amount
    # charged (or a per-unit price if itemized) — it has no way of
    # "knowing" your self-reported quantity, so comparing OCR against the
    # computed per-unit figure would produce false tampering flags on
    # every fractional-quantity complaint. Comparing against amount_paid
    # is what OCR can actually verify.
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
        if abs(ai_extracted_price - amount_paid) > PRICE_MATCH_TOLERANCE_RS:
            triggered_flags.append(
                f"price_mismatch: amount_paid={amount_paid}, ocr_extracted={ai_extracted_price}"
            )
            final_status = ComplaintStatus.suspicious_price_mismatch
    else:
        triggered_flags.append("no_ocr_price_extracted_likely_handwritten")
        final_status = ComplaintStatus.pending_manual_review_handwritten

    if is_coordinated_attack:
        final_status = ComplaintStatus.potential_coordinated_attack

    return _save(final_status)