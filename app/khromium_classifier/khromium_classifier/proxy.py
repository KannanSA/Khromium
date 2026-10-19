# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""OpenAI-compatible proxy. The provider API key stays on this server.

Clients send a license token in ``X-Khromium-License``. This module checks
AI entitlement, then calls OpenAI or xAI with ``KHROMIUM_OPENAI_API_KEY`` or
``KHROMIUM_XAI_API_KEY``. Those keys are never returned to the client and
this module never logs them.
"""

import json
import os
import urllib.request

from khromium_classifier.license_key import verify
from khromium_classifier.provider import DEFAULT_MODELS, ENDPOINTS, api_key_for, normalize_provider


def _redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "")
    return text


def proxy_chat(payload: dict, license_token: str, urlopen=None, now: float | None = None):
    """Forward one chat-completions call if the license has AI entitlement.

    Returns ``(status_code, json_body)``. ``urlopen`` is injectable so tests
    can mock urllib. The server key is attached only to the upstream request.
    """

    status = verify(license_token or "", now=now)
    if not status.get("entitled_ai"):
        return 402, {
            "error": {
                "message": "AI protection is not active",
                "type": "khromium_entitlement",
            }
        }

    provider = normalize_provider(os.environ.get("KHROMIUM_AI_PROVIDER", "openai"))
    key = api_key_for(provider)
    if not key:
        return 503, {
            "error": {
                "message": "Khromium model provider is not configured",
                "type": "khromium_config",
            }
        }

    body = dict(payload) if isinstance(payload, dict) else {}
    body.pop("api_key", None)
    body.pop("authorization", None)
    body["model"] = os.environ.get("KHROMIUM_AI_MODEL", "").strip() or DEFAULT_MODELS[provider]
    encoded = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINTS[provider],
        data=encoded,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    opener = urlopen or urllib.request.urlopen
    try:
        with opener(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except Exception:
        return 502, {
            "error": {
                "message": "upstream model request failed",
                "type": "khromium_upstream",
            }
        }
    raw = _redact(raw, key)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return 502, {
            "error": {
                "message": "upstream returned invalid JSON",
                "type": "khromium_upstream",
            }
        }
    if not isinstance(parsed, dict):
        parsed = {"data": parsed}
    return 200, parsed
