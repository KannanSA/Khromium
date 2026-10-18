# Copyright 2026 The Khromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""OpenAI-compatible chat completions for OpenAI and xAI Grok."""

import json
import os
import urllib.request

from khromium_classifier.prompt import SYSTEM_PROMPT
from khromium_classifier.schema import parse_chat_completion

ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "grok": "https://api.x.ai/v1/chat/completions",
}
DEFAULT_MODELS = {"openai": "gpt-4o-mini", "grok": "grok-3-mini"}


def normalize_provider(name: str) -> str:
    value = (name or "openai").strip().lower()
    if value in ("grok", "xai"):
        return "grok"
    return "openai"


def api_key_for(provider: str) -> str:
    if provider == "grok":
        return os.environ.get("KHROMIUM_XAI_API_KEY", "")
    return os.environ.get("KHROMIUM_OPENAI_API_KEY", "")


def build_request(provider: str, snippet: str, model: str | None = None, api_key: str | None = None):
    provider = normalize_provider(provider)
    key = api_key if api_key is not None else api_key_for(provider)
    body = {
        "model": model or DEFAULT_MODELS[provider],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": snippet[:12000]},
        ],
    }
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
    return request, encoded


def classify_live(provider: str, snippet: str, urlopen=None, model: str | None = None):
    opener = urlopen or urllib.request.urlopen
    request, _encoded = build_request(provider, snippet, model=model)
    # The key is only on the Authorization header. Do not log the request.
    with opener(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
    return parse_chat_completion(raw)
