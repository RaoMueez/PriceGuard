# app/api/routers/ocr_test.py

import json

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends

from app.services.ocr_service import process_receipt, process_handwritten_receipt
from app.schemas.ocr import OCRTestResponse, ExtractPriceResponse
from app.api.deps import get_current_user
from app.models.models import User

router = APIRouter(prefix="/api/test-ocr", tags=["OCR"])


@router.post("", response_model=OCRTestResponse)
async def test_ocr(
    file: UploadFile = File(...),
    item_names: str = Form(..., description='JSON array of item names, e.g. ["Onion", "Tomato"]'),
    receipt_type: str = Form(default="printed", description='"printed" or "handwritten"'),
    current_user: User = Depends(get_current_user),
):
    """
    Temporary/manual testing endpoint. Lets you test either printed or
    handwritten OCR logic directly with a list of item names.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    try:
        cleaned = item_names.strip().replace('\u201c', '"').replace('\u201d', '"')
        requested_items = json.loads(cleaned)
        if not isinstance(requested_items, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f'item_names must be a valid JSON array string, e.g. ["Onion", "Tomato"]. Received: {item_names!r}'
        )

    image_bytes = await file.read()

    try:
        if receipt_type == "handwritten":
            result = process_handwritten_receipt(image_bytes, requested_items)
        else:
            result = process_receipt(image_bytes, requested_items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

    return OCRTestResponse(**result)


@router.post("/extract-price", response_model=ExtractPriceResponse)
async def extract_price_for_complaint(
    file: UploadFile = File(...),
    commodity_name: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    """
    Real endpoint used by the mobile app during complaint submission.
    Tries printed-receipt OCR first (faster, works well for POS receipts);
    if no price is found, tries handwritten-mode OCR as a second attempt.

    This endpoint NEVER raises an error to the caller for OCR failures —
    it always returns a valid response so the app can gracefully fall back
    to manual price entry instead of blocking the complaint flow.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    if not commodity_name or not commodity_name.strip():
        raise HTTPException(status_code=400, detail="commodity_name is required.")

    image_bytes = await file.read()

    # --- Attempt 1: Printed receipt logic ---
    try:
        printed_result = process_receipt(image_bytes, [commodity_name])
        item_result = printed_result.get("extracted_items", {}).get(commodity_name, {})

        if item_result.get("price") is not None:
            return ExtractPriceResponse(
                price=item_result["price"],
                source="ocr_printed",
                auto_detected=True,
            )
    except Exception:
        # Swallow errors here — we still have the handwritten attempt to try
        pass

    # --- Attempt 2: Handwritten receipt logic ---
    try:
        handwritten_result = process_handwritten_receipt(image_bytes, [commodity_name])
        hw_item = handwritten_result.get("extracted_items", {}).get(commodity_name, {})

        if hw_item.get("price") is not None:
            return ExtractPriceResponse(
                price=hw_item["price"],
                source="ocr_handwritten",
                auto_detected=True,
            )
    except Exception:
        pass

    # --- Neither attempt found a price — signal manual entry needed ---
    return ExtractPriceResponse(
        price=None,
        source=None,
        auto_detected=False,
    )