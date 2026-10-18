# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Paid Khromium Shield license tokens.

Token: KHRO1.<base64url json>.<base64url hmac-sha256>
The HMAC covers the middle segment. The default secret is for the owner's
tests only. Set KHROMIUM_LICENSE_HMAC_SECRET before any real deployment.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

DEV_SECRET = "khromium-dev-license-hmac-v1"
PLANS = ("monthly", "yearly", "lifetime")
PRICES_USD = {"monthly": 7.99, "yearly": 69.00}


def secret() -> bytes:
    return os.environ.get("KHROMIUM_LICENSE_HMAC_SECRET", DEV_SECRET).encode()


def license_path() -> Path:
    override = os.environ.get("KHROMIUM_LICENSE_PATH")
    if override:
        return Path(override)
    return Path.home() / ".khromium" / "license.key"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def mint(plan: str, subject: str, days: int = 365, now: float | None = None) -> str:
    if plan not in PLANS:
        raise ValueError("plan must be monthly, yearly, or lifetime")
    if not subject:
        raise ValueError("subject is required")
    issued = int(now if now is not None else time.time())
    if plan == "monthly" and days == 365:
        days = 31
    payload = {"exp": issued + days * 86400, "plan": plan, "sub": subject, "v": 1}
    encoded = _b64url(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    mac = hmac.new(secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"KHRO1.{encoded}.{_b64url(mac)}"


def verify(token: str, now: float | None = None) -> dict:
    current = int(now if now is not None else time.time())
    parts = (token or "").strip().split(".")
    if len(parts) != 3 or parts[0] != "KHRO1":
        return {"entitled": False, "plan": "", "exp": 0, "detail": "license key format is invalid"}
    try:
        payload = json.loads(_b64url_decode(parts[1]))
        mac = _b64url_decode(parts[2])
    except (json.JSONDecodeError, ValueError):
        return {"entitled": False, "plan": "", "exp": 0, "detail": "license key signature is invalid"}
    expected = hmac.new(secret(), parts[1].encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        return {"entitled": False, "plan": "", "exp": 0, "detail": "license key signature is invalid"}
    plan = payload.get("plan", "")
    exp = int(payload.get("exp") or 0)
    if plan not in PLANS or exp <= 0:
        return {"entitled": False, "plan": "", "exp": 0, "detail": "license payload is invalid"}
    if exp <= current:
        return {"entitled": False, "plan": plan, "exp": exp, "detail": "license has expired"}
    return {
        "entitled": True,
        "plan": plan,
        "exp": exp,
        "detail": "paid subscription active",
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
        return {"entitled": False, "plan": "", "exp": 0, "detail": "no license key"}
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
        return {"entitled": False, "plan": "", "exp": 0, "detail": "license server unreachable"}
    if payload.get("active") is True and int(payload.get("exp") or 0) > int(time.time()):
        return {
            "entitled": True,
            "plan": str(payload.get("plan") or ""),
            "exp": int(payload["exp"]),
            "detail": "paid subscription active",
        }
    return {"entitled": False, "plan": "", "exp": 0, "detail": "subscription inactive"}
