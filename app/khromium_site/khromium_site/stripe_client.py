# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Stripe Checkout over the REST API. Card numbers never touch this process."""

import json
import re
import urllib.error
import urllib.request
from urllib.parse import quote

from khromium_site.config import (
    API_VERSION,
    INTEGRATION_IDENTIFIER,
    ConfigError,
    plans,
    price_id,
    public_base,
    secret_key,
)

_SECRET_RE = re.compile(r"\b(?:sk|rk|pk)_(?:test|live)_[A-Za-z0-9]+")
_WEBHOOK_RE = re.compile(r"\bwhsec_[A-Za-z0-9]+")


class StripeError(Exception):
    """Stripe rejected the call or returned something we will not follow."""


def redact(text: str) -> str:
    cleaned = _SECRET_RE.sub("[redacted]", text or "")
    return _WEBHOOK_RE.sub("[redacted]", cleaned)


def encode_form(pairs: list[tuple[str, str]]) -> bytes:
    # Braces stay literal so Stripe can replace {CHECKOUT_SESSION_ID}.
    parts = []
    for key, value in pairs:
        parts.append(f"{quote(str(key), safe='[]')}={quote(str(value), safe='{}')}")
    return "&".join(parts).encode("utf-8")


def _error_message(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "Stripe returned an unexpected response."
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return redact(str(error["message"]))
    return "Stripe returned an unexpected response."


def _checkout_host_ok(url: str) -> bool:
    from urllib.parse import urlsplit

    if not url or any(ch in url for ch in "\r\n\t "):
        return False
    parts = urlsplit(url.strip())
    return parts.scheme == "https" and (parts.hostname or "").lower() == "checkout.stripe.com"


class StripeClient:
    def __init__(self, opener=None):
        self._opener = opener or urllib.request.urlopen

    def _request(self, method: str, path: str, body: bytes | None = None) -> dict:
        key = secret_key()
        request = urllib.request.Request(
            "https://api.stripe.com" + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {key}",
                "Stripe-Version": API_VERSION,
                "User-Agent": "khromium-site/1.0",
            },
        )
        if body is not None:
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            response = self._opener(request, timeout=20)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            raise StripeError(_error_message(raw)) from None
        try:
            raw = response.read()
            code = getattr(response, "status", None)
            if code is None:
                code = getattr(response, "code", 200)
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
        if code >= 400:
            raise StripeError(_error_message(raw))
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StripeError("Stripe returned an unexpected response.") from exc
        if not isinstance(payload, dict):
            raise StripeError("Stripe returned an unexpected response.")
        return payload

    def create_checkout_session(self, plan: str, base_url: str) -> str:
        current = plans()
        if plan not in current:
            raise ConfigError("Choose the browser purchase or the monthly AI plan.")
        spec = current[plan]
        chosen_price = price_id(plan)
        success = f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel = f"{base_url}/"
        # Browser is a one-time Price (mode=payment). Monthly AI is a
        # recurring Price (mode=subscription). Do not send subscription_data
        # on the one-time session.
        fields = [
            ("mode", spec["mode"]),
            ("line_items[0][price]", chosen_price),
            ("line_items[0][quantity]", "1"),
            ("success_url", success),
            ("cancel_url", cancel),
            ("metadata[plan]", plan),
            ("metadata[amount_usd]", spec["amount"]),
            ("metadata[product]", "khromium-shield"),
            ("client_reference_id", plan),
            ("integration_identifier", INTEGRATION_IDENTIFIER),
        ]
        if spec["mode"] == "subscription":
            fields.append(("subscription_data[metadata][plan]", plan))
        body = encode_form(fields)
        payload = self._request("POST", "/v1/checkout/sessions", body)
        url = str(payload.get("url") or "")
        if not _checkout_host_ok(url):
            raise StripeError("Stripe did not return a Checkout URL.")
        return url

    def retrieve_checkout_session(self, session_id: str) -> dict:
        safe = quote(session_id, safe="")
        return self._request(
            "GET",
            f"/v1/checkout/sessions/{safe}?expand[]=subscription",
        )


def checkout_base(bound_port: int | None) -> str:
    return public_base(bound_port)
