# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Stripe webhook signature check (HMAC-SHA256 over timestamp.payload)."""

import hashlib
import hmac
import os
import time

TOLERANCE_SECONDS = 300

FULFILLMENT_TYPES = (
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
)


class SignatureError(Exception):
    """The Stripe-Signature header does not match the payload."""


def webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def sign_payload(secret: str, payload: bytes, timestamp: int) -> str:
    signed = str(int(timestamp)).encode("ascii") + b"." + payload
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={int(timestamp)},v1={digest}"


def verify_signature(
    secret: str,
    payload: bytes,
    header: str,
    now: float | None = None,
) -> None:
    if not secret:
        raise SignatureError("webhook secret is not configured")
    timestamp = ""
    signatures: list[str] = []
    for part in (header or "").split(","):
        key, sep, value = part.strip().partition("=")
        if not sep:
            continue
        if key == "t":
            timestamp = value.strip()
        elif key == "v1":
            signatures.append(value.strip().lower())
    if not timestamp or not signatures:
        raise SignatureError("missing signature")
    try:
        stamp = int(timestamp)
    except ValueError as exc:
        raise SignatureError("bad timestamp") from exc
    current = time.time() if now is None else float(now)
    if abs(current - stamp) > TOLERANCE_SECONDS:
        raise SignatureError("timestamp outside tolerance")
    signed = timestamp.encode("ascii") + b"." + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    matched = False
    for candidate in signatures:
        if len(candidate) == len(expected) and hmac.compare_digest(candidate, expected):
            matched = True
    if not matched:
        raise SignatureError("signature mismatch")
