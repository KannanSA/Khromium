# Khromium launcher

Small native companion for the paid Khromium product. It is the program an owner can ship before a full browser build exists.

It is **not** the Chromium browser (`autoninja chrome` is a separate, much larger build). It is not Google Chrome. Khromium is an independent project and is not affiliated with Google.

What it does:

- Prints the name Khromium
- States the two offers: a one-time browser purchase at **$49.00** (includes 30 days of AI) and monthly AI at **$10.00** (twice the default $5 API cost)
- Opens the local download site with `--open`, or prints how to start that site
- Does not collect card numbers and does not embed Stripe secret keys

Sources in this directory are Khromium-original work under `LICENSE.khromium`.

## Build

Install [Zig](https://ziglang.org/download/) 0.14 or newer. From this directory, on Linux, macOS, or Windows:

```bash
sh build.sh
```

If `zig` is not on `PATH`:

```bash
ZIG=/path/to/zig sh build.sh
```

`build.sh` writes two files at the repo root and checks their headers:

| File | Format |
| --- | --- |
| `dist/khromium-macos-intel` | Mach-O 64-bit x86_64 executable (Intel Mac) |
| `dist/khromium-windows-x64.exe` | PE32+ console executable, x86-64 |

The script also compiles a temporary host binary, checks the printed offers, and checks that `--open` refuses a non-local URL. That host binary is deleted. It is not the Linux download.

No macOS SDK is committed. Zig's bundled libc is enough for this program.

## Run

Intel Mac, from Terminal:

```bash
chmod +x dist/khromium-macos-intel
./dist/khromium-macos-intel
./dist/khromium-macos-intel --open
```

The file is unsigned. macOS may block the first launch until you sign and notarize it, or run it from Terminal.

Windows, from Command Prompt, or by double-clicking the exe:

```bat
dist\khromium-windows-x64.exe
dist\khromium-windows-x64.exe --open
```

A double-click prints the same text in a console window and shows a Khromium dialog. Windows SmartScreen may warn because the file is unsigned.

`--open` with no URL uses `http://127.0.0.1:8787`. `--open URL` accepts only `http://127.0.0.1` or `http://localhost`, with an optional port and path. Any other address is refused.

Start the site that URL points at:

```bash
cd app/khromium_site
python3 -m khromium_site --port 8787
```

The download site serves these two files from `/downloads/khromium-windows` and `/downloads/khromium-macos`. See `app/khromium_site/README.md`.
