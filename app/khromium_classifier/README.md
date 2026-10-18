# Khromium classifier

Companion for Khromium Shield. It uses the same system prompt as `components/khromium/system_prompt.cc` so a DOM snippet can be classified without rebuilding Chromium. The companion is proprietary under `LICENSE.khromium`. Upstream Chromium stays BSD.

The default path is local heuristics. It does not need an API key and it does not check a license.

Paid AI does not ask the customer for `KHROMIUM_OPENAI_API_KEY` or `KHROMIUM_XAI_API_KEY`. The browser sends the license to this service at `POST /v1/chat/completions` (`X-Khromium-License`). The service calls OpenAI or xAI with the **server** key. That key is not returned and not logged.

## Prices

| Offer | What the customer pays | Default |
| --- | --- | --- |
| Browser, one time | `KHROMIUM_BROWSER_PRICE_CENTS` | 4900 ($49.00) |
| Monthly AI | `2 * KHROMIUM_API_COST_CENTS` | 1000 ($10.00) |

The monthly default treats the provider cost as 500 cents ($5.00). That number is a placeholder. Set `KHROMIUM_API_COST_CENTS` to the real cost before charging. Create the Stripe Price `STRIPE_PRICE_AI_MONTHLY` at the same 2× amount. `STRIPE_PRICE_BROWSER` is the one-time Price.

The browser purchase includes 30 days of AI. After that the browser license remains and AI stops. The monthly plan is AI-only. It does not grant lasting browser rights.

## Run

From this directory, with Python 3.10 or newer and no extra packages:

```bash
python3 -m khromium_classifier serve --port 8765
```

Open http://127.0.0.1:8765 and paste HTML.

The browser's default proxy URL is port **8766**:

```bash
export KHROMIUM_OPENAI_API_KEY=...   # server only
export STRIPE_SECRET_KEY=...          # server only, never commit
export STRIPE_PRICE_BROWSER=price_...
export STRIPE_PRICE_AI_MONTHLY=price_...
python3 -m khromium_classifier serve --port 8766
```

Classify a file from the shell with heuristics:

```bash
python3 -m khromium_classifier classify --html snippet.html
```

Mint a license (owner machine, production HMAC secret):

```bash
export KHROMIUM_LICENSE_HMAC_SECRET="replace-with-a-long-random-secret"
python3 -m khromium_classifier mint --plan browser --subject buyer@example.com
python3 -m khromium_classifier mint --plan ai_monthly --subject buyer@example.com
```

Checkout is the download site in `app/khromium_site` (hosted Stripe page, no card form). This companion does not start a second Checkout. A paid browser session includes 30 days of AI. The monthly plan is AI-only.

`KHROMIUM_ALLOW_BYO_KEY=1` is dev-only, off by default. It is the only way `classify --live` calls OpenAI or xAI directly from this machine.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

License, price, and proxy tests mock HTTP. Checkout tests live with the download site. No Stripe secret and no network are required.
