import os
import unittest

from khromium_classifier.license_key import mint, verify


class LicenseTests(unittest.TestCase):
    def test_minted_key_is_entitled(self):
        token = mint("yearly", "kannan@example.com", days=30, now=1_700_000_000)
        status = verify(token, now=1_700_000_000 + 10)
        self.assertTrue(status["entitled"])
        self.assertEqual(status["plan"], "yearly")

    def test_expired_key_is_rejected(self):
        token = mint("monthly", "kannan@example.com", days=1, now=1_700_000_000)
        status = verify(token, now=1_700_000_000 + 3 * 86400)
        self.assertFalse(status["entitled"])
        self.assertIn("expired", status["detail"])

    def test_tampered_signature_is_rejected(self):
        token = mint("lifetime", "kannan@example.com", days=3650, now=1_700_000_000)
        broken = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
        status = verify(broken, now=1_700_000_000)
        self.assertFalse(status["entitled"])

    def test_secret_override(self):
        os.environ["KHROMIUM_LICENSE_HMAC_SECRET"] = "other-secret"
        try:
            token = mint("yearly", "a@b.c", days=10, now=1_700_000_000)
            os.environ["KHROMIUM_LICENSE_HMAC_SECRET"] = "khromium-dev-license-hmac-v1"
            status = verify(token, now=1_700_000_000)
            self.assertFalse(status["entitled"])
        finally:
            os.environ.pop("KHROMIUM_LICENSE_HMAC_SECRET", None)
