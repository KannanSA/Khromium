# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""HTML for the Khromium download site."""

import html
from pathlib import Path

from khromium_site.config import download_targets, plans

_CSS = Path(__file__).resolve().parent / "web" / "site.css"

_MARK = """<svg width="28" height="28" viewBox="0 0 48 48" aria-hidden="true">
<path d="M24 4 L42 14 V34 L24 44 L6 34 V14 Z" fill="none" stroke="currentColor" stroke-width="2.5"/>
<path d="M18 16 V32 M18 24 L30 16 M18 24 L30 32" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

_PLATFORM_SCRIPT = """
<script>
(function () {
  var el = document.getElementById("platform-note");
  if (!el) return;
  var ua = navigator.userAgent || "";
  var name = "";
  if (/Windows/i.test(ua)) name = "Windows";
  else if (/Mac OS X|Macintosh/i.test(ua)) name = "macOS";
  else if (/Linux/i.test(ua) && !/Android/i.test(ua)) name = "Linux";
  if (!name) return;
  el.textContent = "For " + name + ". Windows, macOS, and Linux builds are available after checkout.";
})();
</script>
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _layout(title: str, body: str, *, robots: str = "index,follow", script: str = "") -> str:
    css = _CSS.read_text(encoding="utf-8")
    browser = plans()["browser"]["display"]
    monthly = plans()["ai_monthly"]["display"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="Buy Khromium. {esc(browser)} once, including 30 days of AI, or {esc(monthly)} per month for AI protection. Download for Windows, macOS, and Linux after checkout.">
<meta name="robots" content="{esc(robots)}">
<meta name="theme-color" content="#0f6b4c">
<style>
{css}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site wrap">
  <a class="brand" href="/">{_MARK}<span>Khromium</span></a>
</header>
{body}
<footer>
  <div class="wrap">
    <p>Khromium Shield is paid, closed-source software. Upstream Chromium in the project tree stays under the BSD license.</p>
    <p>Khromium is an independent project and is not affiliated with Google.</p>
    <p>Browser {esc(browser)} once · AI protection {esc(monthly)} per month</p>
  </div>
</footer>
{script}
</body>
</html>
"""


def render_home() -> str:
    offers = plans()
    browser = offers["browser"]
    monthly = offers["ai_monthly"]
    placeholder = ""
    if monthly.get("placeholder"):
        placeholder = (
            f"<p class=\"fine\">The {esc(monthly['display'])} monthly price is "
            f"twice a {esc(monthly['api_cost_display'])} API-cost placeholder. "
            "Set KHROMIUM_API_COST_CENTS to the real provider cost before charging. "
            "The Stripe Price should use that same customer amount.</p>"
        )
    body = f"""
<main id="main">
  <section class="hero wrap">
    <h1>Khromium</h1>
    <p class="promise">Buy the browser once, or subscribe for AI ad-block protection.</p>
    <form class="buy" method="post" action="/checkout">
      <fieldset class="plans" id="plans">
        <legend class="sr-only" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)">Choose a plan</legend>
        <label class="plan">
          <input type="radio" name="plan" value="browser" checked>
          <span class="plan-name">{esc(browser["label"])}</span>
          <span class="plan-price">{esc(browser["display"])}</span>
          <span class="plan-interval">{esc(browser["interval"])}</span>
          <span class="plan-interval">{esc(browser["detail"])}</span>
        </label>
        <label class="plan">
          <input type="radio" name="plan" value="ai_monthly">
          <span class="plan-name">{esc(monthly["label"])}</span>
          <span class="plan-price">{esc(monthly["display"])}</span>
          <span class="plan-interval">{esc(monthly["interval"])}</span>
          <span class="plan-interval">{esc(monthly["detail"])}</span>
        </label>
      </fieldset>
      <button class="cta" type="submit">Get Khromium</button>
      <p class="platform" id="platform-note">For Windows, macOS, and Linux.</p>
      <p class="fine">Checkout comes first. Khromium never sees your card number. Khromium holds the model API key. The license key and downloads are on the success page.</p>
      {placeholder}
    </form>
  </section>
  <section class="band" id="features">
    <div class="wrap features">
      <article>
        {_MARK}
        <h2>Shield reads the wall</h2>
        <p>While AI protection is active, Shield classifies an anti-adblock wall or an obfuscated ad container and clears the overlay. After the 30-day trial, that stops until the monthly AI plan starts. The browser purchase stays valid.</p>
      </article>
      <article>
        {_MARK}
        <h2>Khromium provides the model</h2>
        <p>Trial users and monthly subscribers do not paste an OpenAI or xAI key. The browser sends the license to Khromium's proxy. The provider key stays on the server.</p>
      </article>
      <article>
        {_MARK}
        <h2>Three desktops</h2>
        <p>Windows, macOS, and Linux builds are published by the owner. This page starts Checkout. It does not hand out a free installer.</p>
      </article>
    </div>
  </section>
  <section class="steps wrap">
    <h2>How to get Khromium</h2>
    <ol>
      <li><strong>Choose an offer</strong> The browser is {esc(browser["display"])} once and includes 30 days of AI. Monthly AI is {esc(monthly["display"])} and does not include a lasting browser license.</li>
      <li><strong>Pay on Stripe Checkout</strong> The browser is a one-time payment. Monthly AI is a subscription. Hosted Checkout collects the card. This site only receives the result.</li>
      <li><strong>Copy the key and download</strong> The success page shows the license key and the Windows, macOS, and Linux links.</li>
    </ol>
  </section>
</main>
"""
    return _layout("Khromium", body, script=_PLATFORM_SCRIPT)


def render_message(title: str, detail: str, *, hint: str = "") -> str:
    extra = f"<p>{esc(hint)}</p>" if hint else ""
    body = f"""
<main id="main" class="notice wrap">
  <h1>{esc(title)}</h1>
  <p>{esc(detail)}</p>
  {extra}
  <p><a class="ghost" href="/">Back to Khromium</a></p>
</main>
"""
    return _layout(title, body, robots="noindex")


def render_success(record: dict) -> str:
    plan = plans().get(record.get("plan") or "", {})
    label = plan.get("label", record.get("plan") or "")
    price = plan.get("display", "")
    price_bit = f" ({price})" if price else ""
    links = []
    targets = download_targets()
    placeholder = bool(targets and targets[0].get("placeholders"))
    for row in targets:
        rel = "" if row["href"].startswith("/") else ' rel="noopener noreferrer"'
        links.append(
            f'<a class="download" href="{esc(row["href"])}"{rel}>Download for {esc(row["label"])}</a>'
        )
    note = "Binaries are published by the owner."
    if placeholder:
        note += (
            " These buttons use placeholder /downloads/ paths until "
            "KHROMIUM_DOWNLOAD_URL_WIN, KHROMIUM_DOWNLOAD_URL_MAC, and "
            "KHROMIUM_DOWNLOAD_URL_LINUX point at real builds."
        )
    body = f"""
<main id="main" class="panel wrap">
  <h1>Your Khromium license</h1>
  <p>Payment received for {esc(record.get("email") or "")}. Plan: {esc(label)}{esc(price_bit)}. This key is bound to that email.</p>
  <h2>License key</h2>
  <pre class="license-key" id="license-key">{esc(record.get("key") or "")}</pre>
  <button class="ghost" type="button" id="copy-key">Copy license key</button>
  <h2>Download</h2>
  <div class="downloads">
    {"".join(links)}
  </div>
  <p class="fine">{esc(note)}</p>
  <p class="fine">Put the key in the browser user-data directory as khromium/license.key, or set KHROMIUM_LICENSE_KEY.</p>
</main>
"""
    script = """
<script>
(function () {
  var button = document.getElementById("copy-key");
  var key = document.getElementById("license-key");
  if (!button || !key) return;
  button.addEventListener("click", function () {
    var text = key.textContent || "";
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        button.textContent = "Copied";
      }, function () {
        button.textContent = "Select the key and copy it";
      });
    } else {
      button.textContent = "Select the key and copy it";
    }
  });
})();
</script>
"""
    return _layout("Your Khromium license", body, robots="noindex", script=script)


def render_download_placeholder(name: str) -> str:
    labels = {
        "khromium-windows": "Windows",
        "khromium-macos": "macOS",
        "khromium-linux": "Linux",
    }
    label = labels.get(name, "this platform")
    body = f"""
<main id="main" class="notice wrap">
  <h1>Download for {esc(label)}</h1>
  <p>Binaries are published by the owner. This repository does not contain a Khromium installer, and this address is a placeholder.</p>
  <p>Set KHROMIUM_DOWNLOAD_URL_WIN, KHROMIUM_DOWNLOAD_URL_MAC, and KHROMIUM_DOWNLOAD_URL_LINUX to the real files.</p>
  <p><a class="ghost" href="/">Back to Khromium</a></p>
</main>
"""
    return _layout(f"Download for {label}", body, robots="noindex")
