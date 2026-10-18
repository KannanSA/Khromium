import os
import unittest

from khromium_classifier.license_key import (
    api_cost_cents,
    browser_price_cents,
    customer_monthly_cents,
    mint,
    verify,
)

NOW = 1_700_000_000
DAY = 86400


class LicenseTests(unittest.TestCase):
    def test_browser_trial_then_browser_remains(self):
        token = mint("browser", "kannan@example.com", now=NOW)
        during = verify(token, now=NOW + 29 * DAY)
        self.assertTrue(during["entitled_browser"])
        self.assertTrue(during["entitled_ai"])
        self.assertEqual(during["plan"], "browser")
        self.assertEqual(during["ai_until"], NOW + 30 * DAY)

        ended = verify(token, now=NOW + 30 * DAY)
        self.assertTrue(ended["entitled_browser"])
        self.assertFalse(ended["entitled_ai"])
        self.assertIn("AI protection has ended", ended["detail"])

        later = verify(token, now=NOW + 400 * DAY)
        self.assertTrue(later["entitled_browser"])
        self.assertFalse(later["entitled_ai"])
        self.assertGreater(later["exp"], NOW + 50 * 365 * DAY)

    def test_ai_monthly_is_ai_only_and_ends_with_the_month(self):
        # The monthly plan entitles AI only. Browser rights stay with the
        # one-time browser purchase, including after a month lapses.
        token = mint("ai_monthly", "kannan@example.com", now=NOW)
        during = verify(token, now=NOW + 10 * DAY)
        self.assertTrue(during["entitled_ai"])
        self.assertFalse(during["entitled_browser"])
        self.assertEqual(during["plan"], "ai_monthly")
        self.assertEqual(during["ai_until"], during["exp"])

        lapsed = verify(token, now=during["exp"])
        self.assertFalse(lapsed["entitled_ai"])
        self.assertFalse(lapsed["entitled_browser"])
        self.assertIn("expired", lapsed["detail"])

    def test_tampered_signature_is_rejected(self):
        token = mint("browser", "kannan@example.com", now=NOW)
        broken = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
        status = verify(broken, now=NOW)
        self.assertFalse(status["entitled_browser"])
        self.assertFalse(status["entitled_ai"])

    def test_secret_override(self):
        os.environ["KHROMIUM_LICENSE_HMAC_SECRET"] = "other-secret"
        try:
            token = mint("browser", "a@b.c", now=NOW)
            os.environ["KHROMIUM_LICENSE_HMAC_SECRET"] = "khromium-dev-license-hmac-v1"
            status = verify(token, now=NOW)
            self.assertFalse(status["entitled_browser"])
            self.assertFalse(status["entitled_ai"])
        finally:
            os.environ.pop("KHROMIUM_LICENSE_HMAC_SECRET", None)

    def test_customer_monthly_cents_are_double_api_cost(self):
        previous = os.environ.get("KHROMIUM_API_COST_CENTS")
        try:
            os.environ["KHROMIUM_API_COST_CENTS"] = "750"
            self.assertEqual(api_cost_cents(), 750)
            self.assertEqual(customer_monthly_cents(), 1500)
            self.assertEqual(customer_monthly_cents(400), 800)
        finally:
            if previous is None:
                os.environ.pop("KHROMIUM_API_COST_CENTS", None)
            else:
                os.environ["KHROMIUM_API_COST_CENTS"] = previous

    def test_default_prices_are_placeholders(self):
        previous_api = os.environ.get("KHROMIUM_API_COST_CENTS")
        previous_browser = os.environ.get("KHROMIUM_BROWSER_PRICE_CENTS")
        os.environ.pop("KHROMIUM_API_COST_CENTS", None)
        os.environ.pop("KHROMIUM_BROWSER_PRICE_CENTS", None)
        try:
            self.assertEqual(api_cost_cents(), 500)
            self.assertEqual(customer_monthly_cents(), 1000)
            self.assertEqual(browser_price_cents(), 4900)
        finally:
            if previous_api is None:
                os.environ.pop("KHROMIUM_API_COST_CENTS", None)
            else:
                os.environ["KHROMIUM_API_COST_CENTS"] = previous_api
            if previous_browser is None:
                os.environ.pop("KHROMIUM_BROWSER_PRICE_CENTS", None)
            else:
                os.environ["KHROMIUM_BROWSER_PRICE_CENTS"] = previous_browser
