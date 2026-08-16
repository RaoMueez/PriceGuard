# app/services/cloud_storage_service.py

import os
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)


def upload_receipt_image(image_bytes: bytes) -> str:
    """
    Uploads a receipt image to Cloudinary and returns its permanent,
    publicly-accessible HTTPS URL. Replaces local-disk storage, which
    does not survive Render container restarts.
    """
    result = cloudinary.uploader.upload(
        image_bytes,
        folder="priceguard/receipts",
        resource_type="image",
    )
    return result["secure_url"]