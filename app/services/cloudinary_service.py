from hashlib import sha256
from typing import BinaryIO

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, status

from app.core.config import settings


def upload_medical_file(file_obj: BinaryIO, file_name: str, content_type: str | None) -> dict:
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudinary is not configured on this server",
        )

    payload = file_obj.read()
    file_obj.seek(0)
    checksum = sha256(payload).hexdigest()

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    result = cloudinary.uploader.upload(
        file_obj,
        folder=settings.CLOUDINARY_MEDICAL_FOLDER,
        resource_type="auto",
        type="authenticated",
        use_filename=True,
        unique_filename=True,
    )
    return {
        "bucket_name": "cloudinary",
        "object_key": result["public_id"],
        "secure_url": result.get("secure_url"),
        "bytes": result.get("bytes", len(payload)),
        "checksum_sha256": checksum,
        "mime_type": content_type,
        "file_name": file_name,
    }
