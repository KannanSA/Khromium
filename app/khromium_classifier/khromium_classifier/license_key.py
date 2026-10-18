# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Paid Khromium license tokens.

Token: KHRO1.<base64url json>.<base64url hmac-sha256>
The HMAC covers the middle segment exactly. The default secret is for the
owner's tests only. Set KHROMIUM_LICENSE_HMAC_SECRET before any real
deployment.

Two plans:

- ``browser``: one-time purchase. ``exp`` is far in the future (100 years),
  so the browser license does not expire. ``ai_until`` is 30 days after
  issue, which is the included AI trial.
- ``ai_monthly``: monthly AI subscription. AI-only. It does not grant a
  lasting browser entitlement. ``exp`` and ``ai_until`` are the end of the
  paid month.

``verify`` reports ``entitled_browser`` and ``entitled_ai`` separately.
An ended AI trial does not expire the browser purchase.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

DEV_SECRET = "khromium-dev-license-hmac-v1"
PLANS = ("browser", "ai_monthly")

# Placeholder provider cost until the owner sets KHROMIUM_API_COST_CENTS.
# 500 cents is $5.00 of API cost, so the customer price defaults to $10.00.
DEFAULT_API_COST_CENTS = 500
# One-time browser price. 4900 cents is $49.00.
DEFAULT_BROWSER_PRICE_CENTS = 4900

TRIAL_SECONDS = 30 * 86400
BROWSER_LICENSE_SECONDS = 100 * 365 * 86400
MONTH_SECONDS = 31 * 86400


def secret() -> bytes:
    return os.environ.get("KHROMIUM_LICENSE_HMAC_SECRET", DEV_SECRET).encode()


def license_path() -> Path:
    override = os.environ.get("KHROMIUM_LICENSE_PATH")
    if override:
        return Path(override)
    return Path.home() / ".khromium" / "license.key"


def _env_cents(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    value = int(raw)
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer number of cents")
    return value


def api_cost_cents() -> int:
    """What Khromium pays the model provider per subscriber per month.

    ``KHROMIUM_API_COST_CENTS`` is integer cents. When it is unset the
    default is 500 ($5.00). That default is a placeholder. The owner must
    set it to the real provider cost before charging customers.
    """

    return _env_cents("KHROMIUM_API_COST_CENTS", DEFAULT_API_COST_CENTS)


def customer_monthly_cents(api_cost: int | None = None) -> int:
    """Customer price for the monthly AI plan. Always twice the API cost."""

    cost = api_cost_cents() if api_cost is None else int(api_cost)
    if cost < 0:
        raise ValueError("api cost cents must be non-negative")
    return 2 * cost


def browser_price_cents() -> int:
    """One-time browser price in cents. Default 4900 ($49.00).

    Override with ``KHROMIUM_BROWSER_PRICE_CENTS``. The Stripe Price
    ``STRIPE_PRICE_BROWSER`` should be created at this amount.
    """

    return _env_cents("KHROMIUM_BROWSER_PRICE_CENTS", DEFAULT_BROWSER_PRICE_CENTS)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def mint(
    plan: str,
    subject: str,
    days: int | None = None,
    now: float | None = None,
    exp: int | None = None,
    ai_until: int | None = None,
) -> str:
    if plan not in PLANS:
        raise ValueError("plan must be browser or ai_monthly")
    if not subject or not str(subject).strip():
        raise ValueError("subject is required")
    issued = int(now if now is not None else time.time())
    if plan == "browser":
        token_exp = issued + BROWSER_LICENSE_SECONDS if exp is None else int(exp)
        token_ai = issued + TRIAL_SECONDS if ai_until is None else int(ai_until)
    else:
        period = MONTH_SECONDS if days is None else int(days) * 86400
        token_exp = issued + period if exp is None else int(exp)
        token_ai = token_exp if ai_until is None else int(ai_until)
    payload = {
        "ai_until": int(token_ai),
        "exp": int(token_exp),
        "plan": plan,
        "sub": subject,
        "v": 1,
    }
    encoded = _b64url(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    mac = hmac.new(secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"KHRO1.{encoded}.{_b64url(mac)}"


def _denied(detail: str, plan: str = "", exp: int = 0, ai_until: int = 0, sub: str = "") -> dict:
    return {
        "entitled_browser": False,
        "entitled_ai": False,
        "plan": plan,
        "exp": exp,
        "ai_until": ai_until,
        "sub": sub,
        "detail": detail,
    }


def verify(token: str, now: float | None = None) -> dict:
    current = int(now if now is not None else time.time())
    parts = (token or "").strip().split(".")
    if len(parts) != 3 or parts[0] != "KHRO1":
        return _denied("license key format is invalid")
    try:
        payload = json.loads(_b64url_decode(parts[1]))
        mac = _b64url_decode(parts[2])
    except (json.JSONDecodeError, ValueError):
        return _denied("license key signature is invalid")
    expected = hmac.new(secret(), parts[1].encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        return _denied("license key signature is invalid")
    if not isinstance(payload, dict):
        return _denied("license payload is invalid")
    plan = str(payload.get("plan") or "")
    try:
        exp = int(payload.get("exp") or 0)
        ai_until = int(payload.get("ai_until") or 0)
        version = int(payload.get("v") or 0)
    except (TypeError, ValueError):
        return _denied("license payload is invalid")
    sub = str(payload.get("sub") or "")
    if plan not in PLANS or exp <= 0 or version != 1:
        return _denied("license payload is invalid", plan=plan, exp=exp, ai_until=ai_until, sub=sub)

    # Browser rights last for the browser purchase only. A monthly AI plan
    # never sets entitled_browser, even while the paid month is in the future.
    entitled_browser = plan == "browser" and exp > current
    entitled_ai = ai_until > current and plan in PLANS
    if entitled_browser and entitled_ai:
        detail = "browser license active; AI trial active"
    elif entitled_browser:
        detail = "browser license active; AI protection has ended"
    elif entitled_ai:
        detail = "monthly AI plan active"
    elif plan == "ai_monthly":
        detail = "monthly AI plan has expired"
    elif plan == "browser":
        detail = "browser license has expired"
    else:
        detail = "license has expired"
    return {
        "entitled_browser": entitled_browser,
        "entitled_ai": entitled_ai,
        "plan": plan,
        "exp": exp,
        "ai_until": ai_until,
        "sub": sub,
        "detail": detail,
    }


def load_stored_token() -> str:
    env = os.environ.get("KHROMIUM_LICENSE_KEY", "").strip()
    if env:
        return env
    path = license_path()
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def store_token(token: str) -> None:
    path = license_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token.strip() + "\n", encoding="utf-8")


def current_status() -> dict:
    token = load_stored_token()
    if not token:
        return _denied("no license key")
    server = os.environ.get("KHROMIUM_LICENSE_SERVER", "").strip()
    if server:
        return verify_online(server, token)
    return verify(token)


def verify_online(server: str, token: str) -> dict:
    import urllib.request

    body = json.dumps({"token": token}).encode()
    request = urllib.request.Request(
        server,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode())
    except Exception:
        return _denied("license server unreachable")
    if not isinstance(payload, dict):
        return _denied("subscription inactive")
    plan = str(payload.get("plan") or "")
    try:
        exp = int(payload.get("exp") or 0)
        ai_until = int(payload.get("ai_until") or 0)
    except (TypeError, ValueError):
        return _denied("subscription inactive")
    now = int(time.time())
    entitled_browser = bool(payload.get("entitled_browser"))
    entitled_ai = bool(payload.get("entitled_ai"))
    if "entitled_browser" not in payload and "entitled_ai" not in payload:
        if payload.get("active") is True and plan == "browser" and exp > now:
            entitled_browser = True
        if payload.get("active") is True and ai_until > now:
            entitled_ai = True
    if plan == "ai_monthly":
        entitled_browser = False
    if plan == "browser" and exp and exp <= now:
        entitled_browser = False
    if ai_until and ai_until <= now:
        entitled_ai = False
    if not entitled_browser and not entitled_ai:
        return _denied("subscription inactive", plan=plan, exp=exp, ai_until=ai_until)
    if entitled_browser and entitled_ai:
        detail = "browser license active; AI trial active"
    elif entitled_browser:
        detail = "browser license active; AI protection has ended"
    else:
        detail = "monthly AI plan active"
    return {
        "entitled_browser": entitled_browser,
        "entitled_ai": entitled_ai,
        "plan": plan,
        "exp": exp,
        "ai_until": ai_until,
        "sub": str(payload.get("sub") or ""),
        "detail": detail,
    }
