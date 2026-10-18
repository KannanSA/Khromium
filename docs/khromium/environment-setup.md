# Chromium environment for Khromium

Khromium is a fork of Chromium. The browser build is the upstream Chromium build plus the Khromium sources already in this tree. Do not download a second 30 GB tree if you are already in this checkout. You still need `depot_tools` and `gclient sync` for the dependencies pinned by `DEPS`.

## Disk space

Keep **at least 100 GB free** before `fetch chromium` or `gclient sync`. A full checkout plus one component build is often larger than that. Prefer **150 GB or more** free if you will keep debug symbols or more than one `out/` directory. Running out of disk mid-sync leaves a checkout that is painful to repair.

## 1. Install depot_tools

Linux or macOS:

```bash
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$HOME/depot_tools:$PATH"
```

Put that `export` in your shell profile, and put `depot_tools` **before** any other Python or Git on `PATH`. Do not use `~` in the `PATH` entry; use `$HOME` or an absolute path, or `gclient runhooks` fails.

Windows (cmd, not Cygwin):

```bat
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git C:\src\depot_tools
```

Add `C:\src\depot_tools` to the **front** of the user `Path`. Set `DEPOT_TOOLS_WIN_TOOLCHAIN=0` so depot_tools uses your Visual Studio install. If Visual Studio is not in the default location, also set `vs2026_install` to that path. Open a new command prompt and run `gclient` once so it finishes its own setup.

Confirm:

```bash
gclient --version
```

## 2. Get the Chromium source

### This fork

If you already cloned `KannanSA/Khromium`, stay in that checkout. You do not run `fetch` again.

```bash
cd /path/to/Khromium
gclient sync
```

`gclient sync` downloads the dependencies listed in `DEPS`. It is the large step.

### A fresh upstream checkout

```bash
mkdir ~/chromium && cd ~/chromium
fetch chromium
cd src
```

`fetch chromium` creates `.gclient` and a `src` directory, then syncs. `fetch --nohooks chromium` skips the hooks until build dependencies are installed; run `gclient runhooks` after that. `--no-history` saves time and drops history you would want for rebasing, so prefer a full fetch when you plan to rebase onto upstream.

## 3. Platform build dependencies

### Linux

Chromium's builders use Ubuntu 22.04. From `src`:

```bash
./build/install-build-deps.sh
```

You need root, because the script uses apt. Other distributions are unsupported; notes live at the bottom of `docs/linux/build_instructions.md`. You also need Git and Python 3.9 or newer (`python3` on `PATH`). `depot_tools` can supply a Python if the system one is too old.

### macOS

Install the current Xcode plus the command-line tools. Chromium builds with the Xcode SDK even though the day-to-day build is `autoninja`, not the Xcode IDE. Accept the Xcode license (`sudo xcodebuild -license`). The SDK version Chromium expects is in `docs/mac_build_instructions.md`.

### Windows

Install Visual Studio 2026 (Community is enough) with the **Desktop development with C++** workload, the Windows SDK, and Debugging Tools for Windows. Chromium compiles with `clang-cl` but links against the Visual Studio headers and libraries. Details and the exact installer arguments are in `docs/windows_build_instructions.md`.

The upstream pages are the source of truth when a package name changes:

- `docs/linux/build_instructions.md`
- `docs/mac_build_instructions.md`
- `docs/windows_build_instructions.md`

After the packages are installed, if you used `fetch --nohooks`:

```bash
gclient runhooks
```

## 4. Generate the build

From the Chromium source directory (this repo, or `~/chromium/src`):

```bash
gn gen out/Default
```

A practical `out/Default/args.gn` for day-to-day work. It is a component build without a full debug-symbol link:

```gn
is_debug = false
is_component_build = true
symbol_level = 1
blink_symbol_level = 0
v8_symbol_level = 0
proprietary_codecs = true
ffmpeg_branding = "Chrome"
enable_nacl = false
```

`is_debug = true` is easier to step through and much slower to link. `symbol_level = 2` is full debug info and a large disk user. `is_official_build = true` is for a release binary, not the inner loop.

Edit `out/Default/args.gn`, then run `gn gen out/Default` again. GN regenerates when inputs change; you do not need a new output directory for every edit.

## 5. Build

```bash
autoninja -C out/Default chrome
```

`autoninja` picks a job count. Do not call `ninja` or `siso` directly.

- Linux and macOS binary: `out/Default/chrome`
- Windows binary: `out\Default\chrome.exe`

## 6. Turn Khromium on

The feature flag ships **off**. The profile pref `khromium.ai_shield_enabled` defaults to true, so the flag is the opt-in.

```bash
out/Default/chrome \
  --enable-features=KhromiumAiAdShield \
  --user-data-dir=/tmp/khromium-profile
```

Or open `chrome://flags/#khromium-ai-ad-shield` after the flag metadata is compiled in.

Model credentials stay in the browser process. They are never logged and never sent to renderers.

- `KHROMIUM_OPENAI_API_KEY` for OpenAI
- `KHROMIUM_XAI_API_KEY` for xAI Grok
- optional config file, either
  - `<user-data-dir>/<Profile>/khromium/ai_config.json`, or
  - `<user-data-dir>/Khromium/config.json` if the profile file is absent

```json
{
  "provider": "openai",
  "openai_api_key": "",
  "xai_api_key": "",
  "model": "gpt-4o-mini"
}
```

`provider` is `openai` or `grok` (alias `xai`). An environment variable overrides the key in the file. The profile pref `khromium.provider` is the default when the file does not set `provider`. Endpoints are `https://api.openai.com/v1/chat/completions` and `https://api.x.ai/v1/chat/completions`. Default models are `gpt-4o-mini` and `grok-3-mini`.

Restrict the config file to your user (`chmod 600` on Linux and macOS).

## 7. Keep the fork as a patch set

Keep Khromium commits separate from upstream rolls so they rebase.

```bash
git remote add upstream https://chromium.googlesource.com/chromium/src.git
git fetch upstream
git checkout -b khromium-work
git rebase upstream/main
```

Conflicts usually land in the small hook sites listed in [apply-patches.md](apply-patches.md), not in `components/khromium`, `chrome/browser/khromium`, or `chrome/renderer/khromium`.

Export a series for a Chromium tree you already have:

```bash
git format-patch upstream/main --stdout > /tmp/khromium.patch
# in the other tree:
git am /tmp/khromium.patch
```

Run `gclient sync` after a rebase whenever `DEPS` changes.
