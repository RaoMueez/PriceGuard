# app/api/routers/ocr_test.py

import json

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from app.services.ocr_service import process_receipt
from app.schemas.ocr import OCRTestResponse
from app.api.deps import get_current_user
from app.models.models import User

router = APIRouter(prefix="/api/test-ocr", tags=["OCR Testing (Temporary)"])


@router.post("", response_model=OCRTestResponse)
async def test_ocr(
    file: UploadFile = File(...),
    item_names: str = Form(..., description='JSON array of item names, e.g. ["Onion", "Tomato"]'),
    current_user: User = Depends(get_current_user),
):
    
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
        result = process_receipt(image_bytes, requested_items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

    return OCRTestResponse(**result)