# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Local companion service: heuristics UI and the AI proxy.

Hosted Checkout lives on the download site (`app/khromium_site`). This
process does not start a second Checkout.

The provider API key is used only inside ``proxy_chat``. Request logs are
suppressed because bodies can contain page text and headers can contain a
license token.
"""

import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from khromium_classifier.heuristics import local_decision
from khromium_classifier.license_key import (
    api_cost_cents,
    browser_price_cents,
    customer_monthly_cents,
)
from khromium_classifier.provider import classify_live
from khromium_classifier.proxy import proxy_chat

WEB_ROOT = Path(__file__).resolve().parent / "web"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Request bodies can contain page text. Headers can contain a license
        # token. Do not write them to stdout. Never log provider keys.
        return

    def _send(self, status: int, payload, content_type: str = "application/json"):
        if isinstance(payload, (dict, list)):
            raw = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, str):
            raw = payload.encode("utf-8")
        else:
            raw = payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 200_000:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _path(self) -> urllib.parse.SplitResult:
        return urllib.parse.urlsplit(self.path)

    def _pricing(self) -> dict:
        cost = api_cost_cents()
        monthly = customer_monthly_cents(cost)
        return {
            "product": "Khromium Shield",
            "closed_source": True,
            "browser_price_cents": browser_price_cents(),
            "api_cost_cents": cost,
            "ai_monthly_cents": monthly,
            "ai_monthly_is_double_api_cost": monthly == 2 * cost,
            "browser_includes_ai_trial_days": 30,
            "ai_monthly_entitles_browser": False,
            "detail": (
                "One-time browser purchase includes 30 days of AI protection. "
                "The monthly AI plan is twice KHROMIUM_API_COST_CENTS. "
                "The default API cost of 500 cents is a placeholder. "
                "Khromium holds the provider key on the server."
            ),
        }

    def do_GET(self):
        parsed = self._path()
        if parsed.path.startswith("/api/status") or parsed.path.startswith("/api/pricing"):
            self._send(200, self._pricing())
            return
        if parsed.path in ("/", "/index.html"):
            page = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
            self._send(200, page, "text/html; charset=utf-8")
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        parsed = self._path()
        if parsed.path.startswith("/api/classify"):
            self._classify()
            return
        if parsed.path == "/v1/chat/completions":
            data = self._read_json()
            # Ignore any provider key a client might have attached.
            license_token = self.headers.get("X-Khromium-License", "")
            code, payload = proxy_chat(data, license_token)
            self._send(code, payload)
            return
        self._send(404, {"error": "not found"})

    def _classify(self):
        data = self._read_json()
        html = str(data.get("html") or "")
        if not html.strip():
            self._send(400, {"error": "html is required"})
            return
        # Ignore any API key in the body. Customers do not supply provider keys.
        data.pop("api_key", None)
        if data.get("use_live"):
            if os.environ.get("KHROMIUM_ALLOW_BYO_KEY") != "1":
                self._send(
                    403,
                    {
                        "error": "byo_key_disabled",
                        "detail": (
                            "Paid AI calls the Khromium proxy, which holds the "
                            "provider key. Direct keys are dev-only and require "
                            "KHROMIUM_ALLOW_BYO_KEY=1."
                        ),
                    },
                )
                return
            try:
                decision = classify_live(str(data.get("provider") or "openai"), html)
            except Exception as exc:
                self._send(
                    502,
                    {"error": "model_request_failed", "detail": type(exc).__name__},
                )
                return
        else:
            decision = local_decision(html)
        self._send(200, decision)


def serve(port: int = 8765) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Khromium classifier at http://127.0.0.1:{port}")
    server.serve_forever()
