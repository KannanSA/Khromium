# Khromium Shield is paid and closed source

Khromium Shield (the browser component and the companion classifier) is proprietary commercial software under [LICENSE.khromium](../../LICENSE.khromium).

Upstream Chromium in this tree stays under the BSD license in `LICENSE`. Khromium does not relicense that code. Shipping a binary still means shipping Chromium's copyright notices.

There are two ways to buy. Both are paid. Customers do not paste an OpenAI or xAI key. Khromium holds the provider key on its server and proxies classification calls for trials and subscribers.

## 1. One-time browser purchase

The customer pays once for the Khromium browser. Stripe Checkout uses `mode=payment` and the one-time Price `STRIPE_PRICE_BROWSER`.

- Default price: **$49.00** (`KHROMIUM_BROWSER_PRICE_CENTS=4900`).
- The purchase includes **30 days of AI ad-block protection**.
- After 30 days the browser license stays valid. AI protection stops until the customer starts the monthly AI plan.
- During the trial, Khromium provides the model. The customer does not set `KHROMIUM_OPENAI_API_KEY` or `KHROMIUM_XAI_API_KEY`.

## 2. Monthly AI subscription

This is the other way to get AI protection, and the way to continue it after the browser trial.

- The customer price is **always twice the API cost** Khromium pays the provider for one subscriber for one month.
- Set `KHROMIUM_API_COST_CENTS` to that provider cost, in integer cents. The customer price in cents is `2 * KHROMIUM_API_COST_CENTS`.
- If `KHROMIUM_API_COST_CENTS` is unset, the default API cost is **500 cents ($5.00)**. The customer price is then **$10.00 per month**. That default is a **placeholder**. Set it to the real provider cost before charging anyone.
- Create `STRIPE_PRICE_AI_MONTHLY` in the Stripe Dashboard at that same 2× amount. Checkout uses `mode=subscription`. The site and the companion display the computed 2× price.
- This plan entitles **AI only**. It does not grant a lasting browser license. Browser rights come from the one-time purchase. While the paid month is active, `ai_until` equals `exp`. When the month ends, AI stops. Nothing in this plan keeps the browser entitled after that.

## License token

`KHRO1.<base64url json>.<base64url hmac-sha256>`. The HMAC covers the middle segment. Payload:

| Field | Meaning |
| --- | --- |
| `plan` | `browser` or `ai_monthly` |
| `sub` | email or subject |
| `exp` | Unix expiry of the **browser** entitlement. For `browser`, about 100 years out, so the purchase does not expire. For `ai_monthly`, the end of the paid month. |
| `ai_until` | Unix time when AI protection ends. A new browser purchase sets this to now + 30 days. For `ai_monthly` it equals `exp`. |
| `v` | `1` |

`verify` returns `entitled_browser` and `entitled_ai` separately. AI is entitled only while `ai_until` is in the future. An ended trial is not an ended browser.

The browser calls the model, sends DOM, and records anti-adblock script URLs only while AI is entitled. After the trial, the browser purchase remains valid and those AI paths stop.

## How payment is taken

Hosted Stripe Checkout only. There is no custom card form. Do not collect raw card numbers. Do not commit `STRIPE_SECRET_KEY`.

Environment:

| Variable | Role |
| --- | --- |
| `STRIPE_SECRET_KEY` | Server only. Sent to Stripe. Never logged and never returned to the browser. |
| `STRIPE_PRICE_BROWSER` | One-time Price id. |
| `STRIPE_PRICE_AI_MONTHLY` | Recurring Price id, amount = 2× API cost. |
| `KHROMIUM_BROWSER_PRICE_CENTS` | Display price for the browser. Default `4900`. |
| `KHROMIUM_API_COST_CENTS` | Provider cost per subscriber per month. Default `500` (placeholder). |
| `KHROMIUM_LICENSE_HMAC_SECRET` | HMAC secret. The source default is for tests only. |

The download site in `app/khromium_site` is the only Checkout. It does not collect card numbers.

- `POST /checkout` with `plan=browser` — Checkout `mode=payment` and `STRIPE_PRICE_BROWSER`
- `POST /checkout` with `plan=ai_monthly` — Checkout `mode=subscription` and `STRIPE_PRICE_AI_MONTHLY`
- `GET /success?session_id=...` — mints or extends a license **once per Checkout session id**. An unpaid session does not mint. A paid browser session sets `ai_until` 30 days out. A later paid monthly session for the same email extends AI from the current `ai_until`.

The companion classifier does not start a second Checkout. It serves the AI proxy.

Mint by hand on a machine that has the production HMAC secret:

```bash
export KHROMIUM_LICENSE_HMAC_SECRET="replace-with-a-long-random-secret"
python3 -m khromium_classifier mint --plan browser --subject buyer@example.com
python3 -m khromium_classifier mint --plan ai_monthly --subject buyer@example.com
```

The buyer puts the key in `<user-data-dir>/khromium/license.key` or `KHROMIUM_LICENSE_KEY`.

## Provider key stays on the server

Paid AI sends classification to Khromium:

`POST /v1/chat/completions` with header `X-Khromium-License`.

The browser default URL is `KHROMIUM_AI_PROXY_URL`, which defaults to `http://127.0.0.1:8766/v1/chat/completions`. Run the companion there:

```bash
python3 -m khromium_classifier serve --port 8766
```

The proxy checks the license, then calls OpenAI or xAI with the **server** key (`KHROMIUM_OPENAI_API_KEY` or `KHROMIUM_XAI_API_KEY`, selected by `KHROMIUM_AI_PROVIDER`). That key is not returned to the client and is not logged.

A request without a valid AI entitlement is rejected. The browser does not send the owner's provider key.

`KHROMIUM_ALLOW_BYO_KEY=1` is a **dev-only** override, off by default. It lets the browser call OpenAI or xAI directly with a key on that machine. Do not enable it for customers.

## Optional online license check

When `KHROMIUM_LICENSE_SERVER` is set, the browser POSTs `{"token":"..."}` and expects JSON with `plan`, `exp`, `ai_until`, `entitled_browser`, and `entitled_ai`. A failed or inactive response does **not** fall back to the local HMAC. Use this when you need to revoke a key.

## Honesty about the local check

The development secret `khromium-dev-license-hmac-v1` is in the source so unit tests and the owner's builds can mint keys. Anyone with the binary can extract a client-side secret. Before a public release:

- set `KHROMIUM_LICENSE_HMAC_SECRET` at build/run time
- set `KHROMIUM_LICENSE_SERVER` so expired or refunded keys can be revoked
- make this GitHub repository private if the proprietary sources should not be public

The license text is what makes the product closed source. Hiding the files is a separate hosting choice.
