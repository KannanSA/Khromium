# Khromium Shield is paid and closed source

Khromium Shield (the browser component and the companion classifier) is proprietary commercial software under [LICENSE.khromium](../../LICENSE.khromium).

Upstream Chromium in this tree stays under the BSD license in `LICENSE`. Khromium does not relicense that code. Shipping a binary still means shipping Chromium's copyright notices.

## Price

| Plan | Price | Typical term |
| --- | --- | --- |
| Monthly | $7.99 | 31 days |
| Yearly | $69.00 | 365 days |

One key covers the browser feature and the companion app.

## What a buyer gets

1. A `KHRO1.` license key.
2. The browser calls the model only when `KhromiumAiAdShield` is enabled, `khromium.ai_shield_enabled` is true, and the key is valid.
3. The companion app refuses classification with HTTP 402 until the same style of key is activated.

## How to take payment

This repo does not charge cards itself. A practical setup:

1. Create a Stripe Payment Link (or any checkout) for the monthly and yearly prices.
2. After a successful payment, mint a key on a machine that has the production HMAC secret:

```bash
export KHROMIUM_LICENSE_HMAC_SECRET="replace-with-a-long-random-secret"
python3 -m khromium_classifier mint --plan yearly --subject buyer@example.com --days 365
```

3. Send the key to the buyer. They put it in `<user-data-dir>/khromium/license.key` or `KHROMIUM_LICENSE_KEY`.
4. For a stronger check, run a small license server and set `KHROMIUM_LICENSE_SERVER` to its full verify URL. The browser POSTs `{"token":"..."}` and expects `{"active": true, "plan": "yearly", "exp": <unix>}`. When that variable is set, a failed or inactive response does **not** fall back to the local HMAC.

## Honesty about the local check

The development secret `khromium-dev-license-hmac-v1` is in the source so unit tests and the owner's builds can mint keys. Anyone with the binary can extract a client-side secret. Before a public release:

- set `KHROMIUM_LICENSE_HMAC_SECRET` at build/run time
- set `KHROMIUM_LICENSE_SERVER` so expired or refunded keys can be revoked
- make this GitHub repository private if the proprietary sources should not be public

The license text is what makes the product closed source. Hiding the files is a separate hosting choice.
