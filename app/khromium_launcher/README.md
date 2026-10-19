# Khromium desktop app

Native companion for the paid Khromium product. It is the program an owner can ship before a full browser build exists.

It is **not** the Chromium browser (`autoninja chrome` is a separate, much larger build). Khromium is an independent project and is not affiliated with Google.

What the window shows:

- The title Khromium, the K mark, and the word Khromium
- One line: a one-time browser purchase includes 30 days of AI ad-block. Monthly AI is twice the API cost, and Khromium provides the model key
- A button, and the Enter key, that open only `http://127.0.0.1:8787`

It does not collect card numbers and does not embed Stripe secret keys.

Sources and the logo in this directory are Khromium-original work under `LICENSE.khromium`. The mark is a flat geometric K in deep navy, teal, sea blue, and foam white.

## Build

Install [Zig](https://ziglang.org/download/) 0.14 or newer. From this directory, on Linux, macOS, or Windows:

```bash
sh build.sh
```

If `zig` is not on `PATH`:

```bash
ZIG=/path/to/zig sh build.sh
```

`render_logo.py` redraws `assets/logo.svg` into the PNG, ICO, and ICNS files. That step uses numpy. If it cannot run, `build.sh` keeps the assets already in `assets/`.

`build.sh` writes:

| File | Format |
| --- | --- |
| `dist/Khromium.app` | Intel macOS app bundle. `Contents/MacOS/Khromium` is a Mach-O 64-bit x86_64 executable |
| `dist/Khromium-mac-intel.zip` | That `.app`, for the download site |
| `dist/khromium-windows-x64.exe` | PE32+ GUI executable, x86-64, subsystem WINDOWS |

The Windows link uses `zig build-exe -target x86_64-windows-gnu --subsystem windows` and embeds `assets/logo.ico` plus a version resource (`ProductName` Khromium, `FileDescription`, `OriginalFilename` `khromium-windows-x64.exe`) from `assets/khromium.rc`. If the resource compiler fails, the script still writes a GUI exe and copies `logo.ico` to `dist/`.

The macOS link uses `zig build-exe -target x86_64-macos.10.13`. On Linux, `zig cc -framework Cocoa` does not find an Apple SDK. `build.sh` therefore writes temporary text stubs (not committed) whose install names are:

- `/System/Library/Frameworks/AppKit.framework/Versions/C/AppKit`
- `/System/Library/Frameworks/Foundation.framework/Versions/C/Foundation`
- `/usr/lib/libobjc.A.dylib`

The finished Mach-O load commands point at those system paths. On a Mac, dyld loads the real frameworks and the app opens an NSWindow. If those classes are missing at runtime, the same binary shows a dialog with `/usr/bin/osascript` and opens the site with `/usr/bin/open`.

The script also compiles a temporary host binary, checks the offer text, and deletes it. That host binary is not a Linux download.

No macOS SDK is committed.

## Run

Intel Mac, after unzipping the download (or from `dist/Khromium.app` if you just built it):

```bash
unzip -d /tmp dist/Khromium-mac-intel.zip
open /tmp/Khromium.app
```

The bundle is unsigned. macOS may block the first launch until you choose Open in Finder, or remove the quarantine attribute from a file you trust.

Windows, by double-clicking the exe:

```bat
dist\khromium-windows-x64.exe
```

There is no console window. Enter or the button opens `http://127.0.0.1:8787` in the default browser. Windows SmartScreen may warn because the file is unsigned.

Start the site that address points at:

```bash
cd app/khromium_site
python3 -m khromium_site --port 8787
```

The download site serves `dist/khromium-windows-x64.exe` from `/downloads/khromium-windows` and `dist/Khromium-mac-intel.zip` from `/downloads/khromium-macos`. See `app/khromium_site/README.md`.
