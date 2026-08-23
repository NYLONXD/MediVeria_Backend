from hashlib import sha256
from pathlib import Path
from time import time
from typing import BinaryIO

import cloudinary
import cloudinary.uploader
from cloudinary.utils import private_download_url
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


def delivery_format_for_file(file_name: str | None, source_format: SourceFormat) -> str | None:
    """Return the extension Cloudinary used to identify the original asset.

    Authenticated delivery URLs are signed as their complete path. Omitting a
    PDF/image extension therefore creates a different URL from the uploaded
    original and Cloudinary rejects the request with 401.
    """
    extension = Path(file_name or "").suffix.lower().removeprefix(".")
    if extension == "jpeg":
        return "jpg"
    if extension:
        return extension
    return "pdf" if source_format == SourceFormat.pdf else None


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


def get_signed_url(
    object_key: str,
    resource_type: str = "image",
    delivery_format: str | None = None,
) -> str:
    """Generate a short-lived authenticated-original download URL.

    Cloudinary's CDN delivery signature is rejected for this account's
    authenticated PDFs. Its API download endpoint is designed for protected
    originals and works for the worker and browser previews alike.
    """
    _configure()
    return private_download_url(
        object_key,
        delivery_format,
        expires_at=int(time()) + 300,
        attachment=False,
        resource_type=resource_type,
        type="authenticated",
    )


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
