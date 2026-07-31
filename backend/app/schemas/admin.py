# app/schemas/admin.py

from pydantic import BaseModel


class RateUploadResult(BaseModel):
    total_rows_processed: int
    rates_inserted: int
    skipped_items: list[str]   # item names in file that don't match any commodity
    effective_date: str