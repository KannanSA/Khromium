# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Environment and published prices for the download site."""

import os
import secrets
from urllib.parse import urlsplit

from khromium_classifier import license_key as _license_key


def _price(name: str, fallback: float) -> str:
    table = getattr(_license_key, "PRICES_USD", None) or {}
    return f"{float(table.get(name, fallback)):.2f}"


_MONTHLY = _price("monthly", 7.99)
_YEARLY = _price("yearly", 69.00)

API_VERSION = "2026-09-30.endive"
INTEGRATION_IDENTIFIER = "khromium_shield_checkout_" + "".join(
    secrets.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8)
)

PLANS = {
    "monthly": {
        "amount": _MONTHLY,
        "display": f"${_MONTHLY}",
        "interval": "per month",
        "env": "STRIPE_PRICE_MONTHLY",
        "days": 31,
        "label": "Monthly",
    },
    "yearly": {
        "amount": _YEARLY,
        "display": f"${_YEARLY}",
        "interval": "per year",
        "env": "STRIPE_PRICE_YEARLY",
        "days": 365,
        "label": "Yearly",
    },
}

DOWNLOADS = (
    ("win", "Windows", "KHROMIUM_DOWNLOAD_URL_WIN", "/downloads/khromium-windows"),
    ("mac", "macOS", "KHROMIUM_DOWNLOAD_URL_MAC", "/downloads/khromium-macos"),
    ("linux", "Linux", "KHROMIUM_DOWNLOAD_URL_LINUX", "/downloads/khromium-linux"),
)


class ConfigError(Exception):
    """The site is missing a setting required to start Checkout."""


def secret_key() -> str:
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        raise ConfigError(
            "Set STRIPE_SECRET_KEY to a Stripe secret key (sk_) or restricted key (rk_). "
            "A restricted key is the better choice."
        )
    if key.startswith("pk_"):
        raise ConfigError(
            "STRIPE_SECRET_KEY must be a secret key (sk_) or restricted key (rk_), "
            "not a publishable key."
        )
    if not (key.startswith("sk_") or key.startswith("rk_")):
        raise ConfigError("STRIPE_SECRET_KEY must start with sk_ or rk_.")
    return key


def price_id(plan: str) -> str:
    if plan not in PLANS:
        raise ConfigError("Choose the monthly or yearly plan.")
    spec = PLANS[plan]
    problems: list[str] = []
    try:
        secret_key()
    except ConfigError as exc:
        problems.append(str(exc))
    value = os.environ.get(spec["env"], "").strip()
    if not value:
        problems.append(
            f"Set {spec['env']} to a Stripe Price id. "
            f"The published {spec['label'].lower()} price is {spec['display']}."
        )
    elif not value.startswith("price_"):
        problems.append(f"{spec['env']} must be a Stripe Price id (price_...).")
    if problems:
        raise ConfigError("Checkout is not configured. " + " ".join(problems))
    return value


def public_base(bound_port: int | None) -> str:
    configured = os.environ.get("KHROMIUM_SITE_BASE_URL", "").strip().rstrip("/")
    if configured:
        parts = urlsplit(configured)
        if parts.scheme in ("http", "https") and parts.netloc and not parts.username:
            return configured
        raise ConfigError("KHROMIUM_SITE_BASE_URL must be an http(s) origin.")
    port = bound_port or int(os.environ.get("KHROMIUM_SITE_PORT", "8787"))
    return f"http://127.0.0.1:{port}"


def _safe_download(url: str, fallback: str) -> str:
    value = (url or "").strip()
    if not value:
        return fallback
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    parts = urlsplit(value)
    if parts.scheme in ("http", "https") and parts.netloc and not parts.username:
        return value
    return fallback


def download_targets() -> list[dict]:
    rows = []
    placeholders = True
    for key, label, env_name, fallback in DOWNLOADS:
        href = _safe_download(os.environ.get(env_name, ""), fallback)
        if href != fallback:
            placeholders = False
        rows.append(
            {
                "key": key,
                "label": label,
                "env": env_name,
                "href": href,
                "fallback": fallback,
            }
        )
    for row in rows:
        row["placeholders"] = placeholders
    return rows
