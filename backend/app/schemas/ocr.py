# app/schemas/ocr.py

from pydantic import BaseModel


class OCRTestResponse(BaseModel):
    raw_ocr_text: str
    extracted_items: dict