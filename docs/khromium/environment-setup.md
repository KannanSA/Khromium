# Chromium environment for Khromium

Khromium is a fork of Chromium. The build is the upstream Chromium build plus the Khromium Shield sources in this tree. Do not expect a laptop with a small disk to finish it.

## Disk space

Keep **at least 100 GB free** before `fetch chromium`. A full checkout plus a component debug build is often larger. Prefer **150 GB or more** free if you will keep symbols or more than one `out/` directory.

## 1. depot_tools

Linux or macOS:

```bash
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$PWD/depot_tools:$PATH"
```

Put that `export` in your shell profile. On Windows, clone the same repo, add it to `PATH`, and run `gclient` from a normal command prompt after the install script finishes. Do not use Cygwin.

## 2. Fetch the source

If you are already inside this GitHub checkout (`KannanSA/Khromium`), you do not need a second `fetch`. You still need `depot_tools` on `PATH`, then:

```bash
gclient sync
```

That downloads the dependencies pinned by `DEPS`. It is large.

To create a new upstream checkout instead of using this fork:

```bash
mkdir ~/chromium && cd ~/chromium
fetch chromium
cd src
```

`fetch` runs `gclient sync` for you the first time.

## 3. Platform build dependencies

- **Linux:** from `src/`, run `./build/install-build-deps.sh`. You need a recent Debian or Ubuntu (or a close derivative) and root for apt.
- **macOS:** install the current Xcode and the command-line tools. The macOS SDK that Chromium expects is documented in `docs/mac_build_instructions.md`.
- **Windows:** install Visual Studio with the Desktop development with C++ workload, the Windows SDK, and Debugging Tools for Windows. Details are in `docs/windows_build_instructions.md`.

The upstream docs are the source of truth if a package name changes:

- `docs/linux/build_instructions.md`
- `docs/mac_build_instructions.md`
- `docs/windows_build_instructions.md`

## 4. Generate the build

From the Chromium `src` directory:

```bash
gn gen out/Default
```

A sensible `out/Default/args.gn` for a developer who wants a faster component build:

```gn
is_debug = false
is_component_build = true
symbol_level = 1
blink_symbol_level = 0
proprietary_codecs = true
ffmpeg_branding = "Chrome"
enable_nacl = false
```

`is_debug = true` is easier to step through and much slower to link. `is_official_build = true` is how you would cut a release binary later; it is a poor inner-loop default.

Re-run `gn gen out/Default` after editing `args.gn`.

## 5. Build

```bash
autoninja -C out/Default chrome
```

On Windows the executable is `out\Default\chrome.exe`. On Linux and macOS it is `out/Default/chrome`.

## 6. Turn the paid feature on

The feature flag ships **off**. A license is also required.

```bash
out/Default/chrome \
  --enable-features=KhromiumAiAdShield \
  --user-data-dir=/tmp/khromium-profile
```

Then install a paid key:

- environment variable `KHROMIUM_LICENSE_KEY`, or
- `/tmp/khromium-profile/khromium/license.key`

Model credentials, also never logged and never sent to renderers:

- `KHROMIUM_OPENAI_API_KEY` or `KHROMIUM_XAI_API_KEY`
- optional `<user-data-dir>/khromium/ai_config.json` with `{"provider":"openai"}` or `{"provider":"grok"}`

Optional license server (fail closed, no local HMAC fallback):

```bash
export KHROMIUM_LICENSE_SERVER="https://license.example.com/v1/licenses/verify"
```

## 7. Keep the fork as a patch set

Khromium-original commits should stay in their own commits so they rebase onto upstream Chromium.

```bash
git remote add upstream https://chromium.googlesource.com/chromium/src.git
git fetch upstream
git checkout -b khromium-shield
# ... commits that only add Khromium Shield ...
git rebase upstream/main
```

When a rebase conflicts, it is usually in one of the small hook sites listed in [hooks.md](hooks.md), not in the new directories.

To export a patch series for someone who already has a Chromium tree:

```bash
git format-patch upstream/main --stdout > khromium-shield.patch
# apply elsewhere with:
git am khromium-shield.patch
```

`gclient sync` after a rebase whenever `DEPS` changes.
