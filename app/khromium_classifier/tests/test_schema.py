import json
import unittest

from khromium_classifier.prompt import REQUIRED_JSON_KEYS, SYSTEM_PROMPT
from khromium_classifier.schema import DecisionError, parse_chat_completion, parse_decision


class SchemaTests(unittest.TestCase):
    def test_prompt_requires_json_fields(self):
        for key in REQUIRED_JSON_KEYS:
            self.assertIn(key, SYSTEM_PROMPT)
        self.assertIn("JSON only", SYSTEM_PROMPT)

    def test_strips_fence(self):
        raw = """```json
{"block": true, "selectors": ["#modal"], "restore_scroll": true, "reason": "wall"}
```"""
        decision = parse_decision(raw)
        self.assertTrue(decision["block"])
        self.assertEqual(decision["selectors"], ["#modal"])

    def test_rejects_unsafe_selector(self):
        payload = {
            "block": True,
            "selectors": ["<script>"],
            "restore_scroll": False,
            "reason": "no",
        }
        with self.assertRaises(DecisionError):
            parse_decision(json.dumps(payload))

    def test_chat_completion_body(self):
        body = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "block": False,
                                "selectors": [],
                                "restore_scroll": False,
                                "reason": "ordinary page",
                            }
                        )
                    }
                }
            ]
        }
        decision = parse_chat_completion(json.dumps(body))
        self.assertFalse(decision["block"])
