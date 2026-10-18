# Apply the Khromium sources

The new code is already in this checkout at the Chromium paths below. A few upstream files grew by one call so it runs. Those hooks are the ones that conflict when you rebase onto upstream.

## New directories

| Path | Role |
| --- | --- |
| `components/khromium/mojom/khromium.mojom` | `KhromiumAgent`: `IsEntitled` and `Analyze`. No API key crosses Mojo. |
| `components/khromium/` | Feature flag, prefs names, system prompt, JSON decision parser, script-URL markers |
| `chrome/browser/khromium/` | `SimpleURLLoader` client, config load, domain cache, keyed service, script throttle |
| `chrome/renderer/khromium/` | `content::RenderFrameObserver`, scan script, cleanup script |
| `app/khromium_classifier/` | Companion app. Not part of the Chromium GN build. |
| `docs/khromium/` | Setup, architecture, this file |

## Upstream files touched

| File | Change |
| --- | --- |
| `chrome/renderer/chrome_content_renderer_client.cc` | `RenderFrameCreated` constructs `khromium::KhromiumDetector` for every frame; the detector itself returns unless it is the main frame |
| `chrome/renderer/BUILD.gn` | `//chrome/renderer:renderer` depends on `//chrome/renderer/khromium` |
| `chrome/renderer/DEPS` | allows `+components/khromium` |
| `chrome/browser/chrome_content_browser_client_receiver_bindings.cc` | `RegisterBrowserInterfaceBindersForFrame` binds `khromium::mojom::KhromiumAgent` before the extension-only early return |
| `chrome/browser/chrome_content_browser_client.cc` | `CreateURLLoaderThrottles` adds `AntiAdblockThrottle` |
| `chrome/browser/BUILD.gn` | `//chrome/browser:core` depends on `//chrome/browser/khromium` |
| `chrome/browser/prefs/browser_prefs.cc` | `RegisterProfilePrefs` calls `KhromiumService::RegisterProfilePrefs` |
| `chrome/browser/prefs/BUILD.gn` | depends on `//chrome/browser/khromium` |
| `chrome/browser/about_flags.cc` | `khromium-ai-ad-shield` flag, if present |
| `chrome/browser/flag-metadata.json` | expiry metadata for that flag, if present |

## Copy into another Chromium tree

From the root of that tree, copy the new directories, then replay the hook edits (or `git am` a patch series from this fork).

```bash
cp -a /path/to/Khromium/components/khromium components/khromium
cp -a /path/to/Khromium/chrome/browser/khromium chrome/browser/khromium
cp -a /path/to/Khromium/chrome/renderer/khromium chrome/renderer/khromium
```

### Renderer observer

In `ChromeContentRendererClient::RenderFrameCreated`:

```cpp
#include "chrome/renderer/khromium/khromium_detector.h"
// ...
new khromium::KhromiumDetector(render_frame);
```

In `chrome/renderer/BUILD.gn`, add `"//chrome/renderer/khromium"` to the `renderer` target deps. In `chrome/renderer/DEPS`, add `"+components/khromium"`.

### Mojo binder

In `ChromeContentBrowserClient::RegisterBrowserInterfaceBindersForFrame`, before the extension-scheme early return:

```cpp
#include "chrome/browser/khromium/khromium_service.h"
// inside PopulateChromeFrameBinders or the binder method:
map->Add<khromium::mojom::KhromiumAgent>(
    &khromium::KhromiumService::BindFrameAgent);
```

### Prefs

```cpp
#include "chrome/browser/khromium/khromium_service.h"
// RegisterProfilePrefs:
khromium::KhromiumService::RegisterProfilePrefs(registry);
```

Add `"//chrome/browser/khromium"` to `chrome/browser/prefs/BUILD.gn` and to `//chrome/browser:core`.

### URL loader throttle

At the end of `CreateURLLoaderThrottles`, while still on the UI thread:

```cpp
#include "chrome/browser/khromium/anti_adblock_throttle.h"

GURL khromium_page;
if (content::WebContents* contents = wc_getter.Run()) {
  khromium_page = contents->GetLastCommittedURL();
}
if (auto throttle = khromium::AntiAdblockThrottle::MaybeCreate(
        profile, khromium_page)) {
  result.push_back(std::move(throttle));
}
```

### chrome://flags

```cpp
#include "components/khromium/features.h"

{"khromium-ai-ad-shield",
 "Khromium AI ad and anti-adblock shield",
 "Asks OpenAI or Grok about suspected anti-adblock walls. "
 "Requires an API key in the environment or the Khromium config file. "
 "Disabled by default.",
 kOsDesktop, FEATURE_VALUE_TYPE(khromium::kKhromiumAiAdShield)},
```

And in `chrome/browser/flag-metadata.json`:

```json
{
  "name": "khromium-ai-ad-shield",
  "owners": [ "//chrome/browser/khromium/OWNERS" ],
  "expiry_milestone": 170
}
```

## Compile

See [environment-setup.md](environment-setup.md).

```bash
gn gen out/Default
autoninja -C out/Default chrome
```

You need 100 GB or more free. Do not try to compile Khromium by fetching a second full Chromium tree on top of this one.
