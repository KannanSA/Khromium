# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""HTTP server for the Khromium download site."""

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from khromium_site.config import ConfigError, public_base
from khromium_site.issuance import (
    SESSION_RE,
    IssueResult,
    IssuanceError,
    LicenseStore,
    default_licenses_path,
    issue_from_session,
    payment_allows_license,
)
from khromium_site.pages import (
    render_download_placeholder,
    render_home,
    render_message,
    render_success,
)
from khromium_site.stripe_client import StripeClient, StripeError, redact
from khromium_site.webhook import (
    FULFILLMENT_TYPES,
    SignatureError,
    verify_signature,
    webhook_secret,
)

_DOWNLOAD_NAME = re.compile(r"^[a-z0-9._-]{1,80}$")
_CHECKOUT_LIMIT = 16_384
_WEBHOOK_LIMIT = 1_000_000


class Site:
    def __init__(self, opener=None, licenses_path: Path | None = None):
        self.client = StripeClient(opener=opener)
        self.store = LicenseStore(
            Path(licenses_path) if licenses_path else default_licenses_path()
        )
        self.bound_port: int | None = None

    def handler_class(self):
        site = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):
                # Bodies can carry nothing sensitive today, but do not log them.
                return

            def do_GET(self):
                site.handle_get(self)

            def do_POST(self):
                site.handle_post(self)

        return Handler

    def handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlsplit(handler.path)
        path = parsed.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        if path in ("/", "/index.html"):
            self._html(handler, 200, render_home())
            return
        if path == "/success":
            query = parse_qs(parsed.query)
            session_id = (query.get("session_id") or [""])[0].strip()
            status, page = self.success_page(session_id)
            self._html(handler, status, page, no_store=True)
            return
        if path == "/cancel":
            self._redirect(handler, public_base(self.bound_port) + "/")
            return
        if path.startswith("/downloads/"):
            name = path[len("/downloads/") :]
            if "/" in name or not _DOWNLOAD_NAME.fullmatch(name):
                self._html(handler, 404, render_message("Not found", "That page is not on this site."))
                return
            self._html(handler, 200, render_download_placeholder(name))
            return
        self._html(handler, 404, render_message("Not found", "That page is not on this site."))

    def handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlsplit(handler.path)
        path = parsed.path or "/"
        if path == "/checkout":
            self._post_checkout(handler)
            return
        if path == "/stripe/webhook":
            self._post_webhook(handler)
            return
        self._html(handler, 404, render_message("Not found", "That page is not on this site."))

    def success_page(self, session_id: str) -> tuple[int, str]:
        if not SESSION_RE.fullmatch(session_id or ""):
            return 400, render_message(
                "Missing Checkout Session",
                "Open the success link from Stripe. No license key was issued.",
            )
        try:
            existing = self.store.get(session_id)
        except IssuanceError as exc:
            return 422, render_message("License was not issued", str(exc))
        if existing and existing.get("key"):
            return 200, render_success(existing)
        try:
            session = self.client.retrieve_checkout_session(session_id)
        except ConfigError as exc:
            return 503, render_message("Checkout is not configured", str(exc))
        except StripeError as exc:
            return 502, render_message("Payment could not be confirmed", redact(str(exc)))
        if not isinstance(session, dict):
            return 502, render_message(
                "Payment could not be confirmed",
                "Stripe returned an unexpected response.",
            )
        session = dict(session)
        session["id"] = str(session.get("id") or session_id)
        try:
            result = issue_from_session(session, self.store)
        except IssuanceError as exc:
            return 422, render_message("License was not issued", str(exc))
        return _result_page(result)

    def start_checkout(self, plan: str) -> tuple[int, str, str]:
        try:
            base = public_base(self.bound_port)
            location = self.client.create_checkout_session(plan, base)
        except ConfigError as exc:
            return 503, "", render_message("Checkout is not configured", str(exc))
        except StripeError as exc:
            return 502, "", render_message("Checkout could not start", redact(str(exc)))
        return 303, location, ""

    def process_webhook(self, raw: bytes, header: str) -> tuple[int, dict]:
        secret = webhook_secret()
        if not secret:
            return 503, {"error": "webhook_not_configured"}
        try:
            verify_signature(secret, raw, header or "")
        except SignatureError:
            return 400, {"error": "invalid_signature"}
        try:
            event = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, {"error": "invalid_json"}
        if not isinstance(event, dict):
            return 400, {"error": "invalid_event"}
        if event.get("type") not in FULFILLMENT_TYPES:
            return 200, {"received": True, "issued": False}
        obj = event.get("data") if isinstance(event.get("data"), dict) else {}
        session = obj.get("object") if isinstance(obj, dict) else None
        if not isinstance(session, dict):
            return 400, {"error": "invalid_session"}
        session = dict(session)
        session_id = str(session.get("id") or "")
        if (
            not payment_allows_license(session)
            and isinstance(session.get("subscription"), str)
            and SESSION_RE.fullmatch(session_id)
        ):
            try:
                fetched = self.client.retrieve_checkout_session(session_id)
            except (ConfigError, StripeError) as exc:
                return 502, {"error": "stripe_error", "detail": redact(str(exc))}
            if isinstance(fetched, dict):
                session = dict(fetched)
                session["id"] = str(session.get("id") or session_id)
        try:
            result = issue_from_session(session, self.store)
        except IssuanceError as exc:
            return 422, {"error": "not_issued", "detail": redact(str(exc))}
        if result.reason == "missing_email":
            return 422, {"error": "missing_email"}
        if not result.issued:
            return 200, {"received": True, "issued": False, "reason": result.reason}
        return 200, {"received": True, "issued": True, "plan": result.record["plan"]}

    def _post_checkout(self, handler: BaseHTTPRequestHandler) -> None:
        content_type = (handler.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            self._html(
                handler,
                415,
                render_message("Unsupported checkout request", "Submit the plan form on this site."),
            )
            return
        try:
            raw = _read_body(handler, _CHECKOUT_LIMIT)
        except ValueError:
            self._html(handler, 400, render_message("Bad request", "The checkout form was empty or too large."))
            return
        # Only the plan is read. Card fields are never accepted or stored.
        form = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=False)
        plan = (form.get("plan") or [""])[0].strip().lower()
        status, location, page = self.start_checkout(plan)
        if status == 303:
            self._redirect(handler, location)
            return
        self._html(handler, status, page, no_store=True)

    def _post_webhook(self, handler: BaseHTTPRequestHandler) -> None:
        try:
            raw = _read_body(handler, _WEBHOOK_LIMIT)
        except ValueError:
            self._json(handler, 400, {"error": "bad_body"})
            return
        status, payload = self.process_webhook(raw, handler.headers.get("Stripe-Signature", ""))
        self._json(handler, status, payload)

    def _html(self, handler, status: int, page: str, *, no_store: bool = False) -> None:
        body = page.encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("X-Frame-Options", "DENY")
        handler.send_header("Referrer-Policy", "no-referrer")
        handler.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "form-action 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'",
        )
        handler.send_header("Cache-Control", "no-store" if no_store else "no-cache")
        handler.end_headers()
        handler.wfile.write(body)

    def _json(self, handler, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.end_headers()
        handler.wfile.write(body)

    def _redirect(self, handler, location: str) -> None:
        handler.send_response(303)
        handler.send_header("Location", location)
        handler.send_header("Content-Length", "0")
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()


def _result_page(result: IssueResult) -> tuple[int, str]:
    if result.reason == "unpaid" or not result.issued or not result.record:
        if result.reason == "missing_email":
            return 422, render_message(
                "License was not issued",
                "Stripe did not return a customer email, so no license key was issued.",
            )
        return 402, render_message(
            "Payment is not complete",
            "No license key was issued. Finish Checkout, then open the success link again.",
        )
    return 200, render_success(result.record)


def _read_body(handler: BaseHTTPRequestHandler, limit: int) -> bytes:
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None or not str(raw_length).isdigit():
        raise ValueError("missing length")
    length = int(raw_length)
    if length < 0 or length > limit:
        raise ValueError("bad length")
    return handler.rfile.read(length)


class _ThreadingServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(host: str, port: int, site: Site | None = None) -> None:
    site = site or Site()
    httpd = _ThreadingServer((host, port), site.handler_class())
    site.bound_port = httpd.server_address[1]
    shown = host if host != "0.0.0.0" else "127.0.0.1"
    print(f"Khromium download site at http://{shown}:{site.bound_port}", flush=True)
    print("Stripe settings (values are not printed):", flush=True)
    for name in (
        "STRIPE_SECRET_KEY",
        "STRIPE_PRICE_BROWSER",
        "STRIPE_PRICE_AI_MONTHLY",
        "STRIPE_WEBHOOK_SECRET",
        "KHROMIUM_SITE_BASE_URL",
    ):
        state = "set" if os.environ.get(name, "").strip() else "missing"
        print(f"  {name}: {state}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Serve the Khromium download site.")
    parser.add_argument("--host", default=os.environ.get("KHROMIUM_SITE_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("KHROMIUM_SITE_PORT", "8787")),
    )
    args = parser.parse_args(argv)
    serve(args.host, args.port)
    return 0
