# Where Khromium Shield hooks Chromium

The new code lives in directories that did not exist upstream. A few existing files grow by one call so the new code actually runs.

## New files

| Path in this tree | Role |
| --- | --- |
| `components/khromium/mojom/khromium.mojom` | Renderer ↔ browser interface. No API key. |
| `components/khromium/` | Feature flag, system prompt, JSON decision parser, license token check |
| `chrome/browser/khromium/` | Async model client, domain cache, keyed service, script throttle |
| `chrome/renderer/khromium/` | `RenderFrameObserver`, heuristic script, cleanup script |
| `app/khromium_classifier/` | Paid companion app (not part of the Chromium build) |

## Files modified

| File | Change |
| --- | --- |
| `chrome/renderer/chrome_content_renderer_client.cc` | `RenderFrameCreated` constructs `khromium::KhromiumDetector` for the main frame |
| `chrome/renderer/BUILD.gn` | depends on `//chrome/renderer/khromium` |
| `chrome/browser/chrome_content_browser_client_receiver_bindings.cc` | `RegisterBrowserInterfaceBindersForFrame` binds `khromium::mojom::KhromiumAgent` **before** the extension-only early return |
| `chrome/browser/chrome_content_browser_client.cc` | `CreateURLLoaderThrottles` adds `AntiAdblockThrottle` when the profile is paid and the feature is on |
| `chrome/browser/BUILD.gn` | `//chrome/browser:core` depends on `//chrome/browser/khromium` |
| `chrome/browser/prefs/browser_prefs.cc` | registers `khromium.ai_shield_enabled`, `khromium.provider`, `khromium.cache_ttl_hours` |
| `chrome/browser/prefs/BUILD.gn` | depends on `//chrome/browser/khromium` |

## Which layer is the right one

**DOM: renderer `content::RenderFrameObserver`, not a Blink `MutationObserver` fork.**

Anti-adblock walls are page DOM: `position: fixed`, a high `z-index`, `overflow: hidden` on `html`/`body`, and copy such as "disable your ad blocker". That information does not exist on the URL. A patch inside `third_party/blink/renderer/core/dom` would run on every mutation in every document and would be painful to rebase.

`KhromiumDetector` runs in the renderer after `DidFinishLoad`, in the existing Chrome isolated world (`ISOLATED_WORLD_ID_CHROME_INTERNAL`), using `WebLocalFrame::RequestExecuteScript`. The script is the practical equivalent of a short MutationObserver: it scans once, and C++ schedules one more pass two seconds later for overlays inserted after load. It does not stay attached for the life of the document.

The detector calls `IsEntitled()` before the scan. That is AI entitlement, not the lasting browser purchase. Profiles whose trial or monthly plan has ended never copy DOM into the browser process.

**Browser process for the model, not the renderer.**

`network::SimpleURLLoader` with the profile `SharedURLLoaderFactory` runs on the UI thread and completes through a callback. The UI thread is not blocked. The paid path posts to `KHROMIUM_AI_PROXY_URL` and sends the license in `X-Khromium-License`. It does not send the provider API key. The key stays on the proxy (`KHROMIUM_OPENAI_API_KEY` or `KHROMIUM_XAI_API_KEY` in that process only). It is not logged and it is not part of the Mojo struct. `KHROMIUM_ALLOW_BYO_KEY=1` is a dev-only direct call.

**Network: browser-side `URLLoaderThrottle`, not `subresource_filter`.**

Known anti-adblock libraries (`fuckadblock`, `blockadblock`, and the other markers in `components/khromium/script_patterns.h`) are visible from the script URL. `ChromeContentBrowserClient::CreateURLLoaderThrottles` is the right hook because the throttle can see AI entitlement. A renderer throttle would have to be told the license separately. The throttle is not created after the trial or monthly plan ends.

The throttle does **not** cancel the script. Cancelling it is a signal many anti-adblock kits already look for. It records the URL on `KhromiumService` so the next model snippet for that domain includes it. Hiding the wall stays a DOM action.

`components/subresource_filter` is a list-driven subresource blocker. It is a good place, later, for a compiled ad-URL ruleset. It cannot see an overlay's text or decide that `overflow: hidden` should be cleared. Khromium Shield does not hook it.

**Cleanup stays in Blink's page, driven from the renderer.**

The browser parses the model JSON with `base::JSONReader`, checks the fields, and returns selectors over Mojo. The renderer runs a second isolated-world script that `element.remove()`s those selectors and sets `overflow: auto` on `documentElement` and `body` when `restore_scroll` is true.

## Cache

`chrome/browser/khromium/analysis_cache.cc` stores one decision per registrable domain (`net::registry_controlled_domains::GetDomainAndRegistry`) in `<user-data-dir>/khromium/analysis_cache.json`. The default TTL is 24 hours (`khromium.cache_ttl_hours`). A second navigation to the same domain does not call the API. In-flight requests for the same domain share one call.
