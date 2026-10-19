import json
import unittest

from khromium_classifier.prompt import SYSTEM_PROMPT
from khromium_classifier.provider import build_request, classify_live


class _Response:
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ProviderTests(unittest.TestCase):
    def test_api_key_is_not_in_the_body(self):
        request, encoded = build_request(
            "grok", "<div id='x'>disable your ad blocker</div>", api_key="super-secret-key"
        )
        self.assertNotIn(b"super-secret-key", encoded)
        body = json.loads(encoded.decode())
        self.assertEqual(body["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertEqual(request.get_header("Authorization"), "Bearer super-secret-key")
        self.assertIn("api.x.ai", request.full_url)

    def test_live_parse_uses_mock_transport(self):
        content = json.dumps(
            {
                "block": True,
                "selectors": ["#ab-modal"],
                "restore_scroll": True,
                "reason": "anti-adblock wall",
            }
        )
        body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()

        def opener(request, timeout=20):
            self.assertNotIn(b"super-secret-key", request.data)
            return _Response(body)

        decision = classify_live(
            "openai",
            "<div id='ab-modal'>disable your ad blocker</div>",
            urlopen=opener,
        )
        self.assertTrue(decision["block"])
        self.assertEqual(decision["selectors"], ["#ab-modal"])
