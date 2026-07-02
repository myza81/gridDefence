"""Authentication mechanics: password hashing and access-token issuance.

Deliberately outside the module's architectural scope proper (iam-module.md
§4: "the specific mechanism... is an implementation concern outside
architectural scope") — kept in its own file so the chosen mechanism can be
swapped later (e.g. a vetted JWT library, a server-side session store) without
touching `service.py`'s business logic, which only calls the functions below.

Local username/password authentication only, per Phase 1 scope. No LDAP,
Active Directory, OAuth, OIDC, MFA, or SSO — those are Future Extensions
(iam-module.md §17), structurally supported by `ExternalIdentityMapping` but
not implemented here.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import bcrypt

from app.core.config import get_settings

HASH_ALGORITHM = "bcrypt"


def hash_password(password: str) -> str:
    """Hash a password for storage in `UserCredential.password_hash`.

    Never stored as, or derived from, plaintext (iam-module.md §10).
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time-safe verification against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/unrecognized hash — never treat as a match.
        return False


class InvalidTokenError(Exception):
    """Raised when a presented access token is missing, malformed, expired,
    or fails signature verification."""


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_access_token(user_id: uuid.UUID) -> str:
    """Issue a stateless, HMAC-signed bearer token encoding `user_id` and an
    expiry. Not a formal JWT (no external dependency needed for this scope),
    but the same shape: base64 payload + base64 signature, verified
    server-side on every request via `verify_access_token`.
    """
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + settings.access_token_ttl_seconds,
    }
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        settings.secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    signature_b64 = _b64encode(signature)
    return f"{payload_b64}.{signature_b64}"


def verify_access_token(token: str) -> uuid.UUID:
    """Verify a token's signature and expiry, returning the encoded `user_id`.

    Raises `InvalidTokenError` for any failure — callers must treat this as
    "not authenticated," never fall back to an implicit/default identity.
    """
    settings = get_settings()

    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError as exc:
        raise InvalidTokenError("Malformed token") from exc

    expected_signature = hmac.new(
        settings.secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    try:
        provided_signature = _b64decode(signature_b64)
    except Exception as exc:  # noqa: BLE001 — any decode failure is an invalid token
        raise InvalidTokenError("Malformed token signature") from exc

    if not hmac.compare_digest(expected_signature, provided_signature):
        raise InvalidTokenError("Signature mismatch")

    try:
        payload = json.loads(_b64decode(payload_b64))
    except Exception as exc:  # noqa: BLE001
        raise InvalidTokenError("Malformed token payload") from exc

    if payload.get("exp", 0) < time.time():
        raise InvalidTokenError("Token expired")

    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("Malformed subject") from exc
