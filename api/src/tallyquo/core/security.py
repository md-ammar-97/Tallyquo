"""Shared crypto primitives: OTP codes, opaque tokens, access-token JWTs.

Kept in `core` rather than `identity` because sessions/JWT verification are
consumed by every module's route dependencies, not just identity's own
routes.
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from cryptography.fernet import Fernet

from tallyquo.core.config import get_settings


def generate_otp_code() -> str:
    """Cryptographically random 6-digit code (edgecases.md A2 relies on this
    being unpredictable, not just unique)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def normalize_otp_input(raw: str) -> str:
    """Strips whitespace/separators from a pasted code (edgecases.md A4) --
    e.g. "123 456" -> "123456". Does not affect email normalization, which
    deliberately does nothing beyond citext's case-insensitivity (A5, A6)."""
    return "".join(ch for ch in raw if ch.isdigit())


def hash_otp_code(email: str, code: str) -> bytes:
    """HMAC-peppered so a leaked `otp_code` table alone isn't enough to
    forge codes -- the pepper (secret_key) is never stored in the DB.
    Keyed on email too so the same code for two different emails hashes
    differently."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, f"{email.lower()}:{code}".encode(), hashlib.sha256).digest()


def codes_match(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


def hash_ip(ip: str | None) -> bytes | None:
    if not ip:
        return None
    key = get_settings().secret_key.encode()
    return hmac.new(key, ip.encode(), hashlib.sha256).digest()


def generate_opaque_token() -> str:
    """Refresh tokens: high-entropy, URL-safe, opaque to the client."""
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> bytes:
    # Refresh tokens are already 256 bits of secure randomness -- a plain
    # hash (no pepper needed) is sufficient to make the stored value
    # non-reversible, matching architecture.md's "hashed at rest".
    return hashlib.sha256(token.encode()).digest()


def create_access_token(*, tenant_id: UUID, user_id: UUID, session_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "session_id": str(session_id),
        "iat": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


class InvalidAccessToken(Exception):
    pass


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken(str(exc)) from exc


def _fernet() -> Fernet:
    # Derives a valid 32-byte urlsafe-base64 Fernet key from the
    # configured secret so any string works in config, not just a
    # pre-generated Fernet key -- one less thing to get right at deploy time.
    digest = hashlib.sha256(get_settings().encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_fields(fields: dict[str, str]) -> bytes:
    """payment_instruction.fields_encrypted -- column-level encryption for
    banking details (architecture.md §12)."""
    return _fernet().encrypt(json.dumps(fields).encode())


def decrypt_fields(blob: bytes) -> dict[str, str]:
    return json.loads(_fernet().decrypt(bytes(blob)).decode())


def mask_fields(fields: dict[str, str]) -> dict[str, str]:
    """Never return full banking details from a list/get by default --
    design.md: "UI shows masked values with an explicit reveal action"."""
    masked = {}
    for key, value in fields.items():
        masked[key] = f"****{value[-4:]}" if len(value) > 4 else "****"
    return masked
