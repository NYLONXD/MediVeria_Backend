from hashlib import sha256
from typing import BinaryIO

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.health_records import SourceFormat


def _configure() -> None:
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudinary is not configured on this server",
        )
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


def resource_type_for_source_format(source_format: SourceFormat) -> str:
    """Cloudinary buckets uploads into 'image' vs 'raw' resource types.
    PDFs and images upload as 'image' (Cloudinary can rasterize them);
    DICOM and structured/JSON files upload as 'raw'. Signed URL generation
    needs to match whichever bucket the file actually landed in, or the
    signature won't validate."""
    return "image" if source_format in (SourceFormat.pdf, SourceFormat.image) else "raw"


def upload_medical_file(file_obj: BinaryIO, file_name: str, content_type: str | None) -> dict:
    _configure()

    payload = file_obj.read()
    file_obj.seek(0)
    checksum = sha256(payload).hexdigest()

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
        "resource_type": result.get("resource_type", "image"),
        "secure_url": result.get("secure_url"),
        "bytes": result.get("bytes", len(payload)),
        "checksum_sha256": checksum,
        "mime_type": content_type,
        "file_name": file_name,
    }


def get_signed_url(object_key: str, resource_type: str = "image") -> str:
    """Files are uploaded as `type=authenticated`, so the raw secure_url
    Cloudinary returns is NOT publicly reachable — every view needs a
    signed URL generated on demand, or the frontend has nothing to render.

    NOTE: this signature does not expire on its own (Cloudinary's
    token-based auth adds real expiry, and needs separate setup) — fine
    for now, revisit before production if link-sharing is a concern."""
    _configure()
    url, _ = cloudinary_url(
        object_key,
        resource_type=resource_type,
        type="authenticated",
        sign_url=True,
        secure=True,
    )
    return url


def destroy_asset(object_key: str, resource_type: str = "image") -> None:
    """Used when a virus scan flags a file — removes it from storage
    immediately rather than leaving an infected file sitting in the bucket."""
    _configure()
    cloudinary.uploader.destroy(
        object_key,
        resource_type=resource_type,
        type="authenticated",
        invalidate=True,
    )