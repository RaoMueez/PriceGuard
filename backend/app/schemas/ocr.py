# app/schemas/ocr.py

from pydantic import BaseModel


class OCRTestResponse(BaseModel):
    raw_ocr_text: str
    extracted_items: dict


class ExtractPriceResponse(BaseModel):
    price: float | None
    source: str | None       # "ocr_printed", "ocr_handwritten", or None
    auto_detected: bool