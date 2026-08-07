"""Object storage: `{tenant_id}/` prefix convention, signed URLs, upload-through-API.

architecture.md §11: no public objects, ever; access exclusively via signed
URLs with TTL <= 5 minutes; uploads go through the API (not direct-to-bucket)
so tenant ownership is established before the object exists; content-addressed
filenames deduplicate re-uploads.

Talks to Supabase Storage via its S3-compatible endpoint rather than a
Supabase-specific SDK, so the same client works against any S3-compatible
provider if that ever changes.
"""

import hashlib
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig

from tallyquo.core.config import get_settings

# Minimal magic-byte allow-list for the upload types this product accepts:
# logos, receipts, evidence documents. Extend deliberately, not by widening
# a wildcard — an unrecognized signature is rejected, not guessed at.
_SIGNATURES: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"%PDF-": "application/pdf",
}
_MAX_SIGNATURE_LEN = max(len(sig) for sig in _SIGNATURES)


class UnrecognizedFileType(ValueError):
    """Raised when a file's magic bytes don't match an allowed type.

    Validated by content, never by the client-supplied filename extension
    (architecture.md §11, edgecases.md E13).
    """


def sniff_mime(data: bytes) -> str:
    header = data[:_MAX_SIGNATURE_LEN]
    for signature, mime in _SIGNATURES.items():
        if header.startswith(signature):
            return mime
    raise UnrecognizedFileType(
        "File content doesn't match an accepted type (png, jpeg, gif, pdf)."
    )


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_key(tenant_id: str, *parts: str) -> str:
    """`{tenant_id}/invoices/{invoice_id}/{content_hash}.pdf`-style keys."""
    return "/".join([tenant_id, *parts])


@lru_cache
def _client():
    settings = get_settings()
    if not settings.storage_endpoint_url:
        raise RuntimeError(
            "Storage is not configured — set storage_endpoint_url / "
            "storage_access_key_id / storage_secret_access_key once the "
            "Supabase project exists."
        )
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        region_name=settings.storage_region,
        aws_access_key_id=settings.storage_access_key_id,
        aws_secret_access_key=settings.storage_secret_access_key,
        config=BotoConfig(signature_version="s3v4"),
    )


def upload(tenant_id: str, key_parts: list[str], data: bytes) -> tuple[str, str]:
    """Validates content type by magic bytes, then uploads.

    Returns (object_key, mime_type). Tenant ownership of the *row* that will
    reference this object must already be established by the caller before
    this is invoked — storage never grants existence-implies-ownership.
    """
    mime = sniff_mime(data)
    key = build_key(tenant_id, *key_parts)
    _client().put_object(
        Bucket=get_settings().storage_bucket,
        Key=key,
        Body=data,
        ContentType=mime,
    )
    return key, mime


def signed_url(key: str, ttl_seconds: int | None = None) -> str:
    settings = get_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.storage_bucket, "Key": key},
        ExpiresIn=ttl_seconds or settings.signed_url_ttl_seconds,
    )
