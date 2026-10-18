# Copyright 2026 The Khromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Lightweight HTML heuristics mirrored by the renderer scan script."""

import re

PHRASES = (
    "disable your ad blocker",
    "disable adblock",
    "ad blocker detected",
    "adblock detected",
    "whitelist this site",
    "turn off your ad blocker",
    "please disable your ad blocker",
    "allow ads",
    "adblock plus",
)

SCRIPT_MARKERS = (
    "fuckadblock",
    "blockadblock",
    "antiadblock",
    "adblock-detector",
    "adblockdetect",
    "adbdetect",
)

_OPEN_TAG = re.compile(r"<([a-zA-Z0-9]+)([^>]*)>", re.I)
_ATTR = re.compile(r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(['"])(.*?)\2""", re.S)
_ZINDEX = re.compile(r"z-index\s*:\s*(\d+)", re.I)
_BAIT = re.compile(
    r"ad-banner|adsbox|ad-container|banner-ad|anti-adblock|adblock", re.I
)


def _attrs(raw: str) -> dict:
    return {match.group(1).lower(): match.group(3) for match in _ATTR.finditer(raw)}


def _selector(tag: str, attrs: dict) -> str:
    element_id = attrs.get("id", "").strip()
    if element_id and re.fullmatch(r"[A-Za-z][\w:.-]*", element_id):
        return "#" + element_id
    classes = attrs.get("class", "").split()
    if classes:
        return tag + "".join("." + item for item in classes[:2])
    return tag


def analyze_html(html: str) -> dict:
    selectors = []
    script_hits = []
    scroll_lock = False
    seen = set()
    for match in _OPEN_TAG.finditer(html or ""):
        tag = match.group(1).lower()
        attrs = _attrs(match.group(2))
        style = attrs.get("style", "").lower().replace(" ", "")
        window = re.sub(r"<[^>]+>", " ", html[match.end() : match.end() + 800])
        window_l = re.sub(r"\s+", " ", window).strip().lower()
        if tag in ("html", "body"):
            if "overflow:hidden" in style or "overflow-y:hidden" in style:
                scroll_lock = True
            continue
        if tag == "script":
            src = attrs.get("src", "")
            blob = (src + " " + window_l).lower()
            if any(marker in blob for marker in SCRIPT_MARKERS):
                script_hits.append((src or window.strip())[:200])
            continue
        zmatch = _ZINDEX.search(attrs.get("style", ""))
        high_z = bool(zmatch and int(zmatch.group(1)) >= 1000)
        fixed = "position:fixed" in style or "position:sticky" in style
        phrase = any(phrase in window_l for phrase in PHRASES)
        bait = bool(_BAIT.search(attrs.get("id", "") + " " + attrs.get("class", "")))
        if phrase or (fixed and high_z) or (bait and (fixed or high_z)):
            selector = _selector(tag, attrs)
            if selector not in seen:
                seen.add(selector)
                selectors.append(selector)
        if len(selectors) >= 8:
            break
    suspicious = bool(selectors) or bool(script_hits)
    snippet = html[:8000] if suspicious else ""
    return {
        "suspicious": suspicious,
        "selectors": selectors[:8],
        "scroll_lock": scroll_lock,
        "script_hits": script_hits[:3],
        "snippet": snippet,
    }


def local_decision(html: str) -> dict:
    found = analyze_html(html)
    if not found["suspicious"]:
        return {
            "block": False,
            "selectors": [],
            "restore_scroll": False,
            "reason": "No anti-adblock wall or obfuscated ad container.",
        }
    if found["script_hits"] and not found["selectors"]:
        reason = "Known anti-adblock script pattern."
    elif found["scroll_lock"]:
        reason = "Overlay or scroll-lock consistent with an anti-adblock wall."
    else:
        reason = "Heuristic match for an anti-adblock overlay or obfuscated ad container."
    return {
        "block": True,
        "selectors": found["selectors"],
        "restore_scroll": bool(found["scroll_lock"]),
        "reason": reason,
    }
