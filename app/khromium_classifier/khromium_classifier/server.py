# Copyright 2026 The Khromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Local UI for trying Khromium classifications without rebuilding Chromium."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from khromium_classifier.heuristics import local_decision
from khromium_classifier.provider import classify_live

WEB_ROOT = Path(__file__).resolve().parent / "web"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Request bodies can contain page text. Do not write them to stdout.
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

    def do_GET(self):
        if self.path.startswith("/api/status"):
            self._send(
                200,
                {
                    "product": "Khromium",
                    "closed_source": False,
                    "licensed": True,
                    "detail": "Local heuristics run without an API key. Live calls use KHROMIUM_OPENAI_API_KEY or KHROMIUM_XAI_API_KEY.",
                },
            )
            return
        if self.path in ("/", "/index.html"):
            page = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
            self._send(200, page, "text/html; charset=utf-8")
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/api/classify"):
            data = self._read_json()
            html = str(data.get("html") or "")
            if not html.strip():
                self._send(400, {"error": "html is required"})
                return
            # Ignore any API key in the body. Keys come from the environment.
            data.pop("api_key", None)
            if data.get("use_live"):
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
            return
        self._send(404, {"error": "not found"})


def serve(port: int = 8765) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Khromium classifier at http://127.0.0.1:{port}")
    server.serve_forever()
