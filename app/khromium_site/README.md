# Khromium download site

Public page for **Khromium**. **Get Khromium** starts Stripe Checkout for a one-time browser purchase or a monthly AI plan. After payment, the success page shows one license key and download links for Windows, macOS, and Linux.

This site does not collect card numbers. Checkout is Stripe-hosted. Upstream Chromium in this repo stays under `LICENSE`. This site is Khromium-original work under `LICENSE.khromium`.

Khromium is an independent project and is not affiliated with Google.

## Run

From this directory, with Python 3.10 or newer and no extra packages:

```bash
python3 -m unittest discover -s tests -v
python3 -m khromium_site --port 8787
```

From the repo root:

```bash
python3 app/khromium_site/server.py --port 8787
```

Open http://127.0.0.1:8787

The process prints whether each Stripe variable is set. It does not print the values.

## Prices

| Plan | Published price | Stripe env |
| --- | --- | --- |
| Browser, once | $49.00 by default (`KHROMIUM_BROWSER_PRICE_CENTS`) | `STRIPE_PRICE_BROWSER` |
| Monthly AI | Twice `KHROMIUM_API_COST_CENTS`. Unset default is $5 of API cost, so **$10.00**. | `STRIPE_PRICE_AI_MONTHLY` |

The browser purchase includes 30 days of AI ad-block. After that the browser license remains and AI stops. Monthly AI is AI-only, and Khromium holds the provider key. The page shows those amounts even when the price ids are unset. Checkout then returns a configuration error and does not call Stripe.

## Environment

| Variable | Required | Purpose |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | To charge | Secret key (`sk_test_` / `sk_live_`) or, preferably, a restricted key (`rk_`). Server only. |
| `STRIPE_PRICE_BROWSER` | To sell the browser | One-time Price id (`price_...`) at `KHROMIUM_BROWSER_PRICE_CENTS` (default $49.00). |
| `STRIPE_PRICE_AI_MONTHLY` | To sell monthly AI | Recurring Price id at twice `KHROMIUM_API_COST_CENTS` (default $10.00). |
| `KHROMIUM_BROWSER_PRICE_CENTS` | No | Display price for the browser, in cents. Default `4900`. |
| `KHROMIUM_API_COST_CENTS` | No | Provider cost per subscriber per month, in cents. Default `500` (placeholder). Customer price is double. |
| `KHROMIUM_SITE_BASE_URL` | Behind a proxy | Public origin, no trailing path. Success and cancel URLs are built from this. Locally it defaults to `http://127.0.0.1:<port>`. |
| `KHROMIUM_LICENSE_HMAC_SECRET` | Before a real mint | HMAC secret for `KHRO1.` keys. Tests use the development default. |
| `KHROMIUM_ISSUED_LICENSES_PATH` | No | JSON file of issued keys. Default: `app/khromium_site/data/issued_licenses.json` (gitignored). Same Checkout Session id returns the same key. |
| `STRIPE_WEBHOOK_SECRET` | For webhooks | Signing secret (`whsec_...`). If unset, `POST /stripe/webhook` refuses the call. |
| `KHROMIUM_DOWNLOAD_URL_WIN` | No | Windows build URL. Default `/downloads/khromium-windows`. |
| `KHROMIUM_DOWNLOAD_URL_MAC` | No | macOS build URL. Default `/downloads/khromium-macos`. |
| `KHROMIUM_DOWNLOAD_URL_LINUX` | No | Linux build URL. Default `/downloads/khromium-linux`. |
| `KHROMIUM_SITE_HOST` | No | Bind address. Default `127.0.0.1`. |
| `KHROMIUM_SITE_PORT` | No | Default `8787`. |

Do not commit keys. Do not log `STRIPE_SECRET_KEY`. A publishable key (`pk_`) is rejected.

Keep the issued-license file on disk. If it is deleted, a repeat visit to the same success URL can mint a different key.

## Stripe Dashboard

Use a [Stripe sandbox](https://docs.stripe.com/sandboxes.md) for new development so test data stays off the shared test-mode sandbox. A restricted API key is safer than a secret key.

1. Create a restricted key that can write and read Checkout Sessions. Put it in `STRIPE_SECRET_KEY`.
2. Create a Product for the Khromium browser and a one-time Price at the browser amount (default **$49.00**). Copy the `price_` id to `STRIPE_PRICE_BROWSER`.
3. Create a Product for monthly AI and a recurring Price at **twice** `KHROMIUM_API_COST_CENTS` (default **$10.00** per month). Copy the `price_` id to `STRIPE_PRICE_AI_MONTHLY`.
4. Set `KHROMIUM_API_COST_CENTS` to the real provider cost before charging. The $5 default is a placeholder.
5. Leave payment methods on dynamic Checkout. Do not send `payment_method_types`.
6. Set `KHROMIUM_SITE_BASE_URL` to the origin buyers use. Cancel returns to that origin. Success is `{origin}/success?session_id={CHECKOUT_SESSION_ID}`.
7. For local webhook forwarding:

```bash
stripe listen --forward-to localhost:8787/stripe/webhook
```

Put the CLI signing secret in `STRIPE_WEBHOOK_SECRET`. In the Dashboard, point a webhook endpoint at `https://<your-host>/stripe/webhook` and subscribe it to:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`

Both events, and the success page, call one issuance function. A paid session (or a subscription that is `active` or `trialing`) is stored under its session id. A second call returns the stored key and does not mint another.

A paid browser session mints plan `browser`: the browser entitlement lasts about 100 years and `ai_until` is 30 days out. A paid monthly session mints plan `ai_monthly` for 31 days and does not entitle the browser. The buyer puts the key in `<user-data-dir>/khromium/license.key` or `KHROMIUM_LICENSE_KEY`.

This site does not yet act on renewal, cancellation, refund, dispute, or early-fraud events. Before treating the subscription integration as production-complete, handle `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `charge.dispute.created`, `charge.refunded`, and `radar.early_fraud_warning.created`. Local HMAC keys are not revoked from here. Set `KHROMIUM_LICENSE_SERVER` when a failed or inactive answer must turn Shield off. The [Customer Portal](https://docs.stripe.com/customer-management/integrate-customer-portal.md) is the usual place for buyers to cancel or replace a card.

If you charge customers in the US or the EU, turn on Stripe Tax only after you have an active registration. Enabling `automatic_tax` without one collects no tax and returns no error. See [Collect taxes for recurring payments](https://docs.stripe.com/billing/taxes/collect-taxes.md). This site does not enable automatic tax.

## Downloads

The success page links to the three download env vars. Until you set them, the buttons point at `/downloads/khromium-windows`, `/downloads/khromium-macos`, and `/downloads/khromium-linux`.

`/downloads/khromium-windows` and `/downloads/khromium-macos` serve the launcher executables checked in at the repo root:

- `dist/khromium-windows-x64.exe` — 64-bit Windows launcher (PE32+)
- `dist/khromium-macos-intel` — Intel Mac launcher (Mach-O x86_64)

Those files come from `app/khromium_launcher/`. They are the paid companion that explains the $49 browser purchase and the $10 monthly AI plan, and they can open this site. They are **not** a full Chromium or Khromium browser build. Each response is `application/octet-stream` with `Content-Disposition: attachment`.

`/downloads/khromium-linux` stays an HTML placeholder. There is no Linux launcher in this tree.

Only `http:` and `https:` URLs, or a single-slash path, are accepted. Anything else falls back to the default path.

Set `KHROMIUM_DOWNLOAD_URL_WIN`, `KHROMIUM_DOWNLOAD_URL_MAC`, or `KHROMIUM_DOWNLOAD_URL_LINUX` when the success page should point at a full browser build instead of these routes. Rebuild the launchers with `sh app/khromium_launcher/build.sh` (Zig 0.14 or newer).

## Tests

```bash
cd app/khromium_site
python3 -m unittest discover -s tests -v
```

Stripe HTTP is mocked. No key and no network are required.
