"""Small security helpers: random tokens, token hashing, and signed short-lived values."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


def new_token(nbytes: int = 32) -> str:
    """URL-safe random token (used for session ids, CSRF tokens, OAuth state and nonce)."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Session tokens are stored hashed, so a database leak doesn't expose live sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode(), b.encode())


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign(payload: dict[str, Any], secret: str, max_age_seconds: int) -> str:
    """Return ``body.signature`` where body carries the payload and an expiry time."""
    body = _b64(json.dumps({**payload, "exp": int(time.time()) + max_age_seconds}, separators=(",", ":")).encode())
    signature = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def unsign(value: str | None, secret: str) -> dict[str, Any] | None:
    """Return the payload if the signature is valid and it hasn't expired, else None."""
    if not value or "." not in value:
        return None
    body, signature = value.rsplit(".", 1)
    expected = _b64(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
        return None
    return payload
