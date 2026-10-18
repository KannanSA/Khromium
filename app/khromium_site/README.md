# Khromium download site

Public page for **Khromium Shield**. **Get Khromium** starts a Stripe Checkout subscription. After payment, the success page shows one license key and download links for Windows, macOS, and Linux.

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
| Monthly | $7.99 | `STRIPE_PRICE_MONTHLY` |
| Yearly | $69.00 | `STRIPE_PRICE_YEARLY` |

The page shows those amounts even when the price ids are unset. Checkout then returns a configuration error and does not call Stripe.

## Environment

| Variable | Required | Purpose |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | To charge | Secret key (`sk_test_` / `sk_live_`) or, preferably, a restricted key (`rk_`). Server only. |
| `STRIPE_PRICE_MONTHLY` | To sell monthly | Stripe Price id (`price_...`) for $7.99 per month. |
| `STRIPE_PRICE_YEARLY` | To sell yearly | Stripe Price id (`price_...`) for $69.00 per year. |
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
2. Create one Product named Khromium Shield. Monthly and yearly are two Prices on that same product (two billing intervals, not two tiers).
3. Add a recurring Price of **$7.99 USD** every month. Copy the `price_` id to `STRIPE_PRICE_MONTHLY`.
4. Add a recurring Price of **$69.00 USD** every year. Copy the `price_` id to `STRIPE_PRICE_YEARLY`.
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

The paid term is 31 days monthly and 365 days yearly. The buyer puts the key in `<user-data-dir>/khromium/license.key` or `KHROMIUM_LICENSE_KEY`.

`mint()` is used as-is. When that helper's plans are `monthly` and `yearly`, the token uses those names. When it only accepts `ai_monthly`, the site mints an `ai_monthly` token for the same number of days so `verify()` accepts it and Shield's AI entitlement matches the term. That token does not set the separate browser-purchase entitlement.

This site does not yet act on renewal, cancellation, refund, dispute, or early-fraud events. Before treating the subscription integration as production-complete, handle `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`, `charge.dispute.created`, `charge.refunded`, and `radar.early_fraud_warning.created`. Local HMAC keys are not revoked from here. Set `KHROMIUM_LICENSE_SERVER` when a failed or inactive answer must turn Shield off. The [Customer Portal](https://docs.stripe.com/customer-management/integrate-customer-portal.md) is the usual place for buyers to cancel or replace a card.

If you charge customers in the US or the EU, turn on Stripe Tax only after you have an active registration. Enabling `automatic_tax` without one collects no tax and returns no error. See [Collect taxes for recurring payments](https://docs.stripe.com/billing/taxes/collect-taxes.md). This site does not enable automatic tax.

## Downloads

The success page links to the three download env vars. Until you set them, the buttons point at `/downloads/khromium-windows`, `/downloads/khromium-macos`, and `/downloads/khromium-linux`. Those routes explain that the owner publishes the binaries. Do not commit installer files here.

Only `http:` and `https:` URLs, or a single-slash path, are accepted. Anything else falls back to the placeholder path.

## Tests

```bash
cd app/khromium_site
python3 -m unittest discover -s tests -v
```

Stripe HTTP is mocked. No key and no network are required.
