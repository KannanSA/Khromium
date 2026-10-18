# Copyright 2026 The Khromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Validate the strict JSON object the system prompt requires."""

import json
import re

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_MAX_SELECTORS = 8
_MAX_SELECTOR_LEN = 200
_MAX_REASON_LEN = 400


class DecisionError(ValueError):
    pass


def strip_fence(text: str) -> str:
    raw = text.strip()
    if not raw.startswith("```"):
        return raw
    newline = raw.find("\n")
    if newline == -1:
        return raw
    body = raw[newline + 1 :]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3]
    return body.strip()


def _selector_ok(selector: str) -> bool:
    if not selector or len(selector) > _MAX_SELECTOR_LEN:
        return False
    if "\n" in selector or "\r" in selector:
        return False
    lower = selector.lower()
    if "javascript:" in lower or "expression(" in lower:
        return False
    return not any(ch in selector for ch in "<>`{}")


def parse_decision(text: str) -> dict:
    try:
        payload = json.loads(strip_fence(text))
    except json.JSONDecodeError as exc:
        raise DecisionError("model output is not JSON") from exc
    if not isinstance(payload, dict):
        raise DecisionError("model output is not an object")
    for key in ("block", "selectors", "restore_scroll", "reason"):
        if key not in payload:
            raise DecisionError(f"missing {key}")
    if not isinstance(payload["block"], bool) or not isinstance(
        payload["restore_scroll"], bool
    ):
        raise DecisionError("block and restore_scroll must be booleans")
    if not isinstance(payload["reason"], str):
        raise DecisionError("reason must be a string")
    selectors = payload["selectors"]
    if not isinstance(selectors, list) or len(selectors) > _MAX_SELECTORS:
        raise DecisionError("selectors must be a short list")
    clean = []
    for item in selectors:
        if not isinstance(item, str) or not _selector_ok(item):
            raise DecisionError("unsafe selector")
        clean.append(item)
    return {
        "block": payload["block"],
        "selectors": clean,
        "restore_scroll": payload["restore_scroll"],
        "reason": payload["reason"][:_MAX_REASON_LEN],
    }


def parse_chat_completion(body: str) -> dict:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return parse_decision(body)
    if isinstance(payload, dict) and "block" in payload and "choices" not in payload:
        return parse_decision(body)
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DecisionError("chat completion has no message content") from exc
    if not isinstance(content, str):
        raise DecisionError("message content is not a string")
    return parse_decision(content)
