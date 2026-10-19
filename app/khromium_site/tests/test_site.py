# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

import sys
from pathlib import Path

_CLASSIFIER = Path(__file__).resolve().parents[2] / "khromium_classifier"
if str(_CLASSIFIER) not in sys.path:
    sys.path.insert(0, str(_CLASSIFIER))

import base64
import http.client
import io
import json
import os
import re
import tempfile
import threading
import time
import unittest
import urllib.error
from email.message import Message
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs

from khromium_classifier.license_key import verify
from khromium_site.config import INTEGRATION_IDENTIFIER, plans
from khromium_site.issuance import LicenseStore, default_licenses_path, issue_from_session
from khromium_site.pages import render_home, render_success
from khromium_site.server import Site
from khromium_site.stripe_client import StripeClient
from khromium_site.webhook import sign_payload, verify_signature

ENV_KEYS = (
    "STRIPE_SECRET_KEY",
    "STRIPE_PRICE_BROWSER",
    "STRIPE_PRICE_AI_MONTHLY",
    "STRIPE_PRICE_MONTHLY",
    "STRIPE_PRICE_YEARLY",
    "KHROMIUM_API_COST_CENTS",
    "KHROMIUM_BROWSER_PRICE_CENTS",
    "STRIPE_WEBHOOK_SECRET",
    "KHROMIUM_SITE_BASE_URL",
    "KHROMIUM_DOWNLOAD_URL_WIN",
    "KHROMIUM_DOWNLOAD_URL_MAC",
    "KHROMIUM_DOWNLOAD_URL_LINUX",
    "KHROMIUM_ISSUED_LICENSES_PATH",
    "KHROMIUM_LICENSE_HMAC_SECRET",
    "KHROMIUM_SITE_PORT",
)

KEY_RE = re.compile(r"KHRO1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def close(self):
        return None


def http_error(url: str, status: int, payload: dict):
    return urllib.error.HTTPError(
        url,
        status,
        "error",
        Message(),
        io.BytesIO(json.dumps(payload).encode()),
    )


def payload_of(token: str) -> dict:
    part = token.split(".")[1]
    pad = "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part + pad))


def license_active(status: dict) -> bool:
    if status.get("entitled") is True:
        return True
    return bool(status.get("entitled_browser") or status.get("entitled_ai"))


def paid_session(
    session_id="cs_test_paid12345",
    email="buyer@example.com",
    plan="browser",
    payment_status="paid",
    subscription_status="active",
):
    return {
        "id": session_id,
        "object": "checkout.session",
        "payment_status": payment_status,
        "status": "complete",
        "customer_details": {"email": email},
        "customer_email": None,
        "subscription": {"id": "sub_test_12345678", "status": subscription_status},
        "metadata": {
            "plan": plan,
            "amount_usd": plans()[plan]["amount"],
            "product": "khromium-shield",
        },
    }


class EnvCase(unittest.TestCase):
    def setUp(self):
        self._saved = {key: os.environ.get(key) for key in ENV_KEYS}
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["KHROMIUM_LICENSE_HMAC_SECRET"] = "khromium-dev-license-hmac-v1"

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class PageTests(EnvCase):
    def test_home_html_names_khromium_and_prices(self):
        page = render_home()
        self.assertIn("Khromium", page)
        self.assertIn("Get Khromium", page)
        self.assertIn("$49.00", page)
        self.assertIn("$10.00", page)
        self.assertIn("30 days", page)
        self.assertIn("Windows", page)
        self.assertIn("macOS", page)
        self.assertIn("Linux", page)
        self.assertNotIn("Google Chrome", page)
        self.assertNotIn("google chrome", page.lower())
        self.assertIsNone(re.search(r"\bChrome\b", page))
        self.assertIn("not affiliated with Google", page)
        self.assertIn("Chromium", page)

    def test_default_license_file_is_outside_git(self):
        path = default_licenses_path()
        self.assertEqual(path.name, "issued_licenses.json")
        self.assertEqual(path.parent.name, "data")
        ignore = Path(__file__).resolve().parents[1] / ".gitignore"
        self.assertIn("data/", ignore.read_text(encoding="utf-8"))

    def test_javascript_download_url_is_not_used(self):
        os.environ["KHROMIUM_DOWNLOAD_URL_WIN"] = "javascript:alert(1)"
        page = render_success(
            {
                "key": "KHRO1.example.example",
                "email": "buyer@example.com",
                "plan": "browser",
            }
        )
        self.assertNotIn("javascript:", page)
        self.assertIn("/downloads/khromium-windows", page)
        self.assertIn("buyer@example.com", page)
        self.assertNotIn("<script>alert", page)


class CheckoutTests(EnvCase):
    def setUp(self):
        super().setUp()
        self.requests = []

    def opener(self, request, timeout=20):
        headers = {key.lower(): value for key, value in request.header_items()}
        auth = headers.get("authorization", "")
        self.requests.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "body": request.data.decode() if request.data else "",
                "stripe_version": headers.get("stripe-version", ""),
                "auth_matches": auth == "Bearer " + os.environ.get("STRIPE_SECRET_KEY", ""),
            }
        )
        return FakeResponse(
            {
                "id": "cs_test_checkout123",
                "url": "https://checkout.stripe.com/c/pay/cs_test_checkout123",
            }
        )

    def test_checkout_posts_price_amount_and_subscription_mode(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
        os.environ["STRIPE_PRICE_BROWSER"] = "price_browser_test"
        os.environ["STRIPE_PRICE_AI_MONTHLY"] = "price_ai_test"
        client = StripeClient(opener=self.opener)
        cases = (
            ("browser", "payment", "price_browser_test", "49.00"),
            ("ai_monthly", "subscription", "price_ai_test", "10.00"),
        )
        for plan, mode, price, amount in cases:
            url = client.create_checkout_session(plan, "http://127.0.0.1:8787")
            self.assertEqual(url, "https://checkout.stripe.com/c/pay/cs_test_checkout123")
            sent = self.requests[-1]
            self.assertEqual(sent["method"], "POST")
            self.assertTrue(sent["url"].endswith("/v1/checkout/sessions"))
            self.assertEqual(sent["stripe_version"], "2026-09-30.endive")
            self.assertTrue(sent["auth_matches"])
            self.assertNotIn("payment_method_types", sent["body"])
            self.assertIn("{CHECKOUT_SESSION_ID}", sent["body"])
            self.assertNotIn("%7BCHECKOUT_SESSION_ID%7D", sent["body"])
            parsed = parse_qs(sent["body"])
            self.assertEqual(parsed["mode"], [mode])
            if mode == "subscription":
                self.assertEqual(parsed["subscription_data[metadata][plan]"], [plan])
            else:
                self.assertNotIn("subscription_data[metadata][plan]", parsed)
            self.assertEqual(parsed["line_items[0][price]"], [price])
            self.assertEqual(parsed["line_items[0][quantity]"], ["1"])
            self.assertEqual(parsed["metadata[amount_usd]"], [amount])
            self.assertEqual(parsed["metadata[plan]"], [plan])
            self.assertEqual(
                parsed["success_url"],
                ["http://127.0.0.1:8787/success?session_id={CHECKOUT_SESSION_ID}"],
            )
            self.assertEqual(parsed["cancel_url"], ["http://127.0.0.1:8787/"])
            self.assertEqual(parsed["integration_identifier"], [INTEGRATION_IDENTIFIER])
            self.assertRegex(INTEGRATION_IDENTIFIER, r"^khromium_shield_checkout_[a-z]{8}$")

    def test_missing_price_does_not_call_stripe_or_leak_the_secret(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_supersecretvalue"
        called = []

        def opener(request, timeout=20):
            called.append(request.full_url)
            raise AssertionError("Stripe was called")

        with tempfile.TemporaryDirectory() as tmp:
            site = Site(opener=opener, licenses_path=Path(tmp) / "issued.json")
            status, _location, page = site.start_checkout("browser")
        self.assertEqual(called, [])
        self.assertEqual(status, 503)
        self.assertIn("STRIPE_PRICE_BROWSER", page)
        self.assertIn("$49.00", page)
        self.assertNotIn("sk_test_supersecretvalue", page)
        self.assertNotIn("Google Chrome", page)


class IssuanceTests(EnvCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = LicenseStore(Path(self.tmp.name) / "issued.json")

    def tearDown(self):
        self.tmp.cleanup()
        super().tearDown()

    def test_unpaid_session_does_not_mint(self):
        session = paid_session(
            session_id="cs_test_unpaid1234",
            payment_status="unpaid",
            subscription_status="incomplete",
            plan="browser",
        )
        result = issue_from_session(session, self.store, now=1_700_000_000)
        self.assertFalse(result.issued)
        self.assertEqual(result.reason, "unpaid")
        self.assertFalse((Path(self.tmp.name) / "issued.json").exists())

    def test_paid_session_mints_a_key_verify_accepts(self):
        session = paid_session()
        result = issue_from_session(session, self.store, now=1_700_000_000)
        self.assertTrue(result.issued)
        token = result.record["key"]
        status = verify(token, now=1_700_000_000 + 10)
        self.assertTrue(license_active(status))
        self.assertEqual(result.record["plan"], "browser")
        payload = payload_of(token)
        self.assertEqual(payload["sub"], "buyer@example.com")
        self.assertEqual(payload["ai_until"], 1_700_000_000 + 30 * 86400)
        later = verify(token, now=1_700_000_000 + 31 * 86400)
        self.assertTrue(later["entitled_browser"])
        self.assertFalse(later["entitled_ai"])
        again = issue_from_session(session, self.store, now=1_800_000_000)
        self.assertEqual(again.record["key"], token)

    def test_paid_monthly_session_is_ai_only(self):
        session = paid_session(
            session_id="cs_test_month12345",
            email="ai@example.com",
            plan="ai_monthly",
            payment_status="paid",
            subscription_status="active",
        )
        result = issue_from_session(session, self.store, now=1_700_000_000)
        status = verify(result.record["key"], now=1_700_000_000 + 10)
        self.assertTrue(status["entitled_ai"])
        self.assertFalse(status["entitled_browser"])
        self.assertEqual(result.record["plan"], "ai_monthly")
        self.assertEqual(payload_of(result.record["key"])["sub"], "ai@example.com")

    def test_customer_email_field_is_accepted(self):
        session = paid_session(session_id="cs_test_emailfield1", email="")
        session["customer_details"] = {}
        session["customer_email"] = "from-field@example.com"
        result = issue_from_session(session, self.store, now=1_700_000_000)
        self.assertEqual(payload_of(result.record["key"])["sub"], "from-field@example.com")

    def test_email_is_escaped_on_the_success_page(self):
        session = paid_session(
            session_id="cs_test_escape12345",
            email="<script>alert(1)</script>@example.com",
        )
        result = issue_from_session(session, self.store, now=1_700_000_000)
        page = render_success(result.record)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn(result.record["key"], page)


class WebhookTests(EnvCase):
    def test_signature_reject_and_accept(self):
        secret = "whsec_test_secret"
        payload = b'{"id":"evt_test_1"}'
        stamp = 1_700_000_000
        good = sign_payload(secret, payload, stamp)
        verify_signature(secret, payload, good, now=stamp)
        with self.assertRaises(Exception):
            verify_signature(secret, payload, "t=%d,v1=%s" % (stamp, "ab" * 32), now=stamp)
        with self.assertRaises(Exception):
            verify_signature(secret, b"tampered", good, now=stamp)
        with self.assertRaises(Exception):
            verify_signature(secret, payload, good, now=stamp + 1000)


class ServerTests(EnvCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.sessions = {}
        self.fail_if_called = False
        self.calls = []
        self.site = Site(
            opener=self.opener,
            licenses_path=Path(self.tmp.name) / "issued.json",
        )
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.site.handler_class())
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.site.bound_port = self.port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self._wait_until_up()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()
        self.tmp.cleanup()
        super().tearDown()

    def _wait_until_up(self):
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                status, _headers, body = self.request("GET", "/")
            except OSError:
                time.sleep(0.02)
                continue
            if status == 200 and b"Khromium" in body:
                return
        self.fail("download site did not start")

    def opener(self, request, timeout=20):
        if self.fail_if_called:
            raise AssertionError("Stripe HTTP was called")
        headers = {key.lower(): value for key, value in request.header_items()}
        body = request.data.decode() if request.data else ""
        self.calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "body": body,
                "auth": headers.get("authorization", ""),
            }
        )
        if request.get_method() == "POST":
            return FakeResponse(
                {
                    "id": "cs_test_checkout123",
                    "url": "https://checkout.stripe.com/c/pay/cs_test_checkout123",
                }
            )
        session_id = request.full_url.split("/v1/checkout/sessions/")[1].split("?")[0]
        session = self.sessions.get(session_id)
        if session is None:
            raise http_error(
                request.full_url,
                404,
                {"error": {"message": "No such checkout session"}},
            )
        return FakeResponse(session)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        status = response.status
        header_map = {key.lower(): value for key, value in response.getheaders()}
        connection.close()
        return status, header_map, payload

    def test_home_http_page(self):
        status, headers, body = self.request("GET", "/")
        page = body.decode()
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["content-type"])
        self.assertIn("Khromium", page)
        self.assertIn("$49.00", page)
        self.assertIn("$10.00", page)
        self.assertIn("30 days", page)
        self.assertIn("Get Khromium", page)
        self.assertNotIn("Google Chrome", page)
        self.assertIsNone(re.search(r"\bChrome\b", page))
        self.assertIn("frame-ancestors 'none'", headers["content-security-policy"])

    def test_checkout_redirects_to_stripe(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
        os.environ["STRIPE_PRICE_BROWSER"] = "price_browser_test"
        status, headers, _body = self.request(
            "POST",
            "/checkout",
            body=b"plan=browser",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(status, 303)
        self.assertEqual(
            headers["location"],
            "https://checkout.stripe.com/c/pay/cs_test_checkout123",
        )
        self.assertEqual(self.calls[0]["method"], "POST")
        parsed = parse_qs(self.calls[0]["body"])
        self.assertEqual(parsed["mode"], ["payment"])
        self.assertEqual(parsed["line_items[0][price]"], ["price_browser_test"])
        self.assertEqual(parsed["metadata[amount_usd]"], ["49.00"])
        self.assertNotIn("subscription_data[metadata][plan]", parsed)
        self.assertIn("{CHECKOUT_SESSION_ID}", parsed["success_url"][0])
        self.assertTrue(parsed["cancel_url"][0].endswith("/"))

    def test_unconfigured_checkout_names_the_price(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_supersecretvalue"
        self.fail_if_called = True
        status, _headers, body = self.request(
            "POST",
            "/checkout",
            body=b"plan=ai_monthly",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        page = body.decode()
        self.assertEqual(status, 503)
        self.assertIn("STRIPE_PRICE_AI_MONTHLY", page)
        self.assertIn("$10.00", page)
        self.assertNotIn("sk_test_supersecretvalue", page)
        self.assertEqual(self.calls, [])

    def test_unpaid_success_page_does_not_mint(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
        session_id = "cs_test_unpaid1234"
        self.sessions[session_id] = paid_session(
            session_id=session_id,
            payment_status="unpaid",
            subscription_status="incomplete",
            plan="browser",
        )
        status, _headers, body = self.request("GET", f"/success?session_id={session_id}")
        page = body.decode()
        self.assertEqual(status, 402)
        self.assertIn("No license key was issued", page)
        self.assertNotIn("KHRO1.", page)
        self.assertFalse((Path(self.tmp.name) / "issued.json").exists())

    def test_paid_success_page_and_webhook_share_one_key(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
        session = paid_session()
        raw = json.dumps(
            {
                "id": "evt_test_paid",
                "type": "checkout.session.completed",
                "data": {"object": session},
            }
        ).encode()
        stamp = int(time.time())
        bad_status, _bad_headers, bad_body = self.request(
            "POST",
            "/stripe/webhook",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": f"t={stamp},v1={'ab' * 32}",
            },
        )
        self.assertEqual(bad_status, 400)
        self.assertIn(b"invalid_signature", bad_body)
        self.assertFalse((Path(self.tmp.name) / "issued.json").exists())

        status, _headers, body = self.request(
            "POST",
            "/stripe/webhook",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": sign_payload("whsec_test_secret", raw, stamp),
            },
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["issued"])
        self.assertNotIn("KHRO1.", body.decode())
        stored = json.loads((Path(self.tmp.name) / "issued.json").read_text(encoding="utf-8"))
        token = stored["sessions"][session["id"]]["key"]
        self.assertTrue(license_active(verify(token)))

        page_status, _page_headers, page_body = self.request(
            "GET",
            f"/success?session_id={session['id']}",
        )
        page = page_body.decode()
        self.assertEqual(page_status, 200)
        self.assertIn(token, page)
        self.assertEqual(KEY_RE.findall(page), [token])
        self.assertIn("Download for Windows", page)
        self.assertIn("Download for macOS", page)
        self.assertIn("Download for Linux", page)
        self.assertIn("/downloads/khromium-windows", page)
        self.assertIn("Binaries are published by the owner", page)

        again_status, _again_headers, again_body = self.request(
            "POST",
            "/stripe/webhook",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": sign_payload("whsec_test_secret", raw, stamp),
            },
        )
        self.assertEqual(again_status, 200)
        stored_again = json.loads((Path(self.tmp.name) / "issued.json").read_text(encoding="utf-8"))
        self.assertEqual(stored_again["sessions"][session["id"]]["key"], token)

    def test_webhook_without_secret_does_not_mint(self):
        session = paid_session(session_id="cs_test_nosecret123")
        raw = json.dumps(
            {"type": "checkout.session.completed", "data": {"object": session}}
        ).encode()
        status, _headers, body = self.request(
            "POST",
            "/stripe/webhook",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": sign_payload("whsec_test_secret", raw, int(time.time())),
            },
        )
        self.assertEqual(status, 503)
        self.assertIn(b"webhook_not_configured", body)
        self.assertFalse((Path(self.tmp.name) / "issued.json").exists())

    def test_placeholder_download_page(self):
        status, headers, body = self.request("GET", "/downloads/khromium-linux")
        page = body.decode()
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["content-type"])
        self.assertIn("Binaries are published by the owner", page)
        self.assertIn("Linux", page)
        self.assertNotIn("KHRO1.", page)
        self.assertFalse(body.startswith(b"MZ"))
        self.assertNotEqual(body[:4], b"\xcf\xfa\xed\xfe")
        self.assertNotEqual(body[:4], b"\xfe\xed\xfa\xcf")

    def test_windows_and_macos_downloads_are_launchers(self):
        root = Path(__file__).resolve().parents[3]
        cases = (
            (
                "/downloads/khromium-windows",
                root / "dist" / "khromium-windows-x64.exe",
                "khromium-windows-x64.exe",
            ),
            (
                "/downloads/khromium-macos",
                root / "dist" / "khromium-macos-intel",
                "khromium-macos-intel",
            ),
        )
        for path, disk, filename in cases:
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertEqual(body, disk.read_bytes(), path)
            self.assertEqual(headers.get("content-length"), str(len(body)))
            self.assertNotIn("text/html", headers.get("content-type", ""))
            self.assertEqual(headers.get("x-content-type-options"), "nosniff")
            disposition = headers.get("content-disposition", "")
            self.assertIn("attachment", disposition)
            self.assertIn(f'filename="{filename}"', disposition)
            self.assertNotIn(b"KHRO1.", body)
            self.assertNotIn(b"sk_live_", body)
            self.assertNotIn(b"sk_test_", body)

        win_status, _win_headers, win_body = self.request("GET", "/downloads/khromium-windows")
        self.assertEqual(win_status, 200)
        self.assertTrue(win_body.startswith(b"MZ"))
        pe_offset = int.from_bytes(win_body[0x3C:0x40], "little")
        self.assertEqual(win_body[pe_offset : pe_offset + 4], b"PE\x00\x00")
        self.assertEqual(int.from_bytes(win_body[pe_offset + 4 : pe_offset + 6], "little"), 0x8664)
        self.assertEqual(int.from_bytes(win_body[pe_offset + 24 : pe_offset + 26], "little"), 0x20B)

        mac_status, _mac_headers, mac_body = self.request("GET", "/downloads/khromium-macos")
        self.assertEqual(mac_status, 200)
        self.assertIn(mac_body[:4], (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf"))
        magic = int.from_bytes(mac_body[:4], "little")
        self.assertIn(magic, (0xFEEDFACF, 0xCFFAEDFE))
        if magic == 0xFEEDFACF:
            cputype = int.from_bytes(mac_body[4:8], "little")
        else:
            cputype = int.from_bytes(mac_body[4:8], "big")
        self.assertEqual(cputype, 0x01000007)


if __name__ == "__main__":
    unittest.main()
