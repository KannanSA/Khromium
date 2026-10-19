import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from khromium_classifier.server import Handler

HTML = """
<div id="ab-modal" style="position: fixed; z-index: 99999">
Please disable your ad blocker
</div>
"""


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()

    def _request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def test_classify_returns_schema(self):
        status, body = self._request("/api/status")
        self.assertEqual(status, 200)
        self.assertTrue(body["closed_source"])
        self.assertEqual(body["ai_monthly_cents"], 2 * body["api_cost_cents"])
        self.assertIn("browser_price_cents", body)

        status, body = self._request("/api/classify", {"html": HTML})
        self.assertEqual(status, 200)
        self.assertTrue(body["block"])
        self.assertIn("#ab-modal", body["selectors"])
        self.assertIn("restore_scroll", body)
        self.assertIn("reason", body)
        self.assertIsInstance(body["restore_scroll"], bool)

    def test_empty_html_is_rejected(self):
        status, body = self._request("/api/classify", {"html": "   "})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "html is required")

    def test_proxy_rejects_missing_license(self):
        status, body = self._request(
            "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertEqual(status, 402)
        self.assertEqual(body["error"]["type"], "khromium_entitlement")

    def test_ui_is_served(self):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/")
        with urllib.request.urlopen(request, timeout=5) as response:
            page = response.read().decode()
        self.assertEqual(response.status, 200)
        self.assertIn("Khromium", page)
        self.assertIn("Classify", page)
