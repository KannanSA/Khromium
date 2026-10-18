import json
import os
import unittest

from khromium_classifier.license_key import mint
from khromium_classifier.proxy import proxy_chat

NOW = 1_700_000_000
DAY = 86400
SERVER_KEY = "sk-server-secret-not-for-clients"


class _Response:
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self._previous = os.environ.get("KHROMIUM_OPENAI_API_KEY")
        self._provider = os.environ.get("KHROMIUM_AI_PROVIDER")
        os.environ["KHROMIUM_OPENAI_API_KEY"] = SERVER_KEY
        os.environ["KHROMIUM_AI_PROVIDER"] = "openai"

    def tearDown(self):
        if self._previous is None:
            os.environ.pop("KHROMIUM_OPENAI_API_KEY", None)
        else:
            os.environ["KHROMIUM_OPENAI_API_KEY"] = self._previous
        if self._provider is None:
            os.environ.pop("KHROMIUM_AI_PROVIDER", None)
        else:
            os.environ["KHROMIUM_AI_PROVIDER"] = self._provider

    def test_missing_ai_entitlement_does_not_call_upstream(self):
        expired = mint("browser", "buyer@example.com", now=NOW - 40 * DAY)

        def opener(request, timeout=20):
            raise AssertionError("upstream was called without AI entitlement")

        code, body = proxy_chat(
            {"messages": [{"role": "user", "content": "hi"}]},
            expired,
            urlopen=opener,
            now=NOW,
        )
        self.assertEqual(code, 402)
        self.assertEqual(body["error"]["type"], "khromium_entitlement")
        self.assertNotIn(SERVER_KEY, json.dumps(body))

        code, body = proxy_chat(
            {"messages": [{"role": "user", "content": "hi"}]},
            "",
            urlopen=opener,
            now=NOW,
        )
        self.assertEqual(code, 402)

    def test_entitled_call_uses_server_key_and_hides_it(self):
        token = mint("browser", "buyer@example.com", now=NOW)
        seen = {}

        def opener(request, timeout=20):
            seen["auth"] = request.get_header("Authorization")
            seen["url"] = request.full_url
            seen["body"] = request.data
            echo = json.dumps(
                {
                    "choices": [
                        {"message": {"content": "classified " + SERVER_KEY}}
                    ]
                }
            ).encode()
            return _Response(echo)

        code, body = proxy_chat(
            {"messages": [{"role": "user", "content": "<div>disable adblock</div>"}]},
            token,
            urlopen=opener,
            now=NOW,
        )
        self.assertEqual(code, 200)
        self.assertEqual(seen["auth"], "Bearer " + SERVER_KEY)
        self.assertIn("api.openai.com", seen["url"])
        self.assertNotIn(SERVER_KEY.encode(), seen["body"])
        rendered = json.dumps(body)
        self.assertNotIn(SERVER_KEY, rendered)
        self.assertIn("classified ", rendered)

    def test_monthly_plan_can_call_until_exp(self):
        token = mint("ai_monthly", "buyer@example.com", now=NOW)

        def opener(request, timeout=20):
            self.assertEqual(request.get_header("Authorization"), "Bearer " + SERVER_KEY)
            return _Response(b'{"choices":[{"message":{"content":"ok"}}]}')

        code, body = proxy_chat({"messages": []}, token, urlopen=opener, now=NOW + DAY)
        self.assertEqual(code, 200)
        self.assertNotIn(SERVER_KEY, json.dumps(body))

        code, _body = proxy_chat(
            {"messages": []},
            token,
            urlopen=opener,
            now=NOW + 40 * DAY,
        )
        self.assertEqual(code, 402)
