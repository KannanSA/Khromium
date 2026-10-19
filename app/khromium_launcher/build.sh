#!/bin/sh
# Build the Khromium launcher for Intel macOS and 64-bit Windows.
# Requires Zig 0.14 or newer: https://ziglang.org/download/
# Override the compiler with ZIG=/path/to/zig if it is not on PATH.

set -eu

HERE=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)
OUT="$ROOT/dist"
ZIG=${ZIG:-zig}

if ! command -v "$ZIG" >/dev/null 2>&1; then
  echo "zig was not found. Install Zig 0.14 or newer, or set ZIG=/path/to/zig." >&2
  exit 1
fi

mkdir -p "$OUT"

echo "Using $("$ZIG" version)"

"$ZIG" cc -target x86_64-macos -std=c11 -Wall -Wextra -Werror -O2 -s \
  -o "$OUT/khromium-macos-intel" "$HERE/main.c"

"$ZIG" cc -target x86_64-windows -std=c11 -Wall -Wextra -Werror -O2 -s \
  -o "$OUT/khromium-windows-x64.exe" "$HERE/main.c" -luser32 -lshell32

chmod 755 "$OUT/khromium-macos-intel" "$OUT/khromium-windows-x64.exe"

python3 - "$OUT/khromium-macos-intel" "$OUT/khromium-windows-x64.exe" <<'PY'
import struct
import sys

mac_path, win_path = sys.argv[1:]
mac = open(mac_path, "rb").read(32)
magic, cputype = struct.unpack_from("<II", mac, 0)
if magic != 0xFEEDFACF:
    raise SystemExit(f"macOS binary is not 64-bit Mach-O (magic {magic:#x})")
if cputype != 0x01000007:
    raise SystemExit(f"macOS binary is not x86_64 (cputype {cputype:#x})")
win = open(win_path, "rb").read()
if not win.startswith(b"MZ"):
    raise SystemExit("Windows binary does not start with MZ")
pe = struct.unpack_from("<I", win, 0x3C)[0]
if win[pe : pe + 4] != b"PE\0\0":
    raise SystemExit("Windows binary has no PE signature")
machine, = struct.unpack_from("<H", win, pe + 4)
if machine != 0x8664:
    raise SystemExit(f"Windows binary is not x86-64 (machine {machine:#x})")
optional, = struct.unpack_from("<H", win, pe + 24)
if optional != 0x20B:
    raise SystemExit(f"Windows binary is not PE32+ (optional magic {optional:#x})")
print("Mach-O x86_64 and PE32+ x86-64 headers ok")
PY

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
# Host binary is only a smoke test. It is not a published Linux download.
# -Wno-gcc-install-dir-libstdcxx avoids a Zig/Clang host-toolchain note on Linux.
"$ZIG" cc -std=c11 -Wall -Wextra -Werror -Wno-gcc-install-dir-libstdcxx -O2 -s \
  -o "$TMP/khromium-host" "$HERE/main.c"
"$TMP/khromium-host" >"$TMP/out"
"$TMP/khromium-host" --help >"$TMP/help"
grep -F -q 'Khromium' "$TMP/out"
grep -F -q '$49.00' "$TMP/out"
grep -F -q '$10.00' "$TMP/out"
grep -F -q '30 days' "$TMP/out"
grep -F -q 'python3 -m khromium_site --port 8787' "$TMP/out"
grep -F -q 'not Google Chrome' "$TMP/out"
grep -F -q 'does not collect card numbers' "$TMP/out"
if grep -E -q 'sk_live_|sk_test_|whsec_|rk_live_' "$TMP/out" "$TMP/help"; then
  echo "launcher output contains a secret-shaped token" >&2
  exit 1
fi
if "$TMP/khromium-host" --open 'https://example.com' >"$TMP/bad.out" 2>"$TMP/bad.err"; then
  echo "launcher opened a non-local URL" >&2
  exit 1
fi
if "$TMP/khromium-host" --open 'http://127.0.0.1.evil.example' >"$TMP/bad2.out" 2>"$TMP/bad2.err"; then
  echo "launcher accepted a lookalike host" >&2
  exit 1
fi
if "$TMP/khromium-host" --open 'http://127.0.0.1:8787/../secret' >"$TMP/bad4.out" 2>"$TMP/bad4.err"; then
  echo "launcher accepted a dot-dot path" >&2
  exit 1
fi
if "$TMP/khromium-host" --nope >"$TMP/bad3.out" 2>"$TMP/bad3.err"; then
  echo "launcher accepted an unknown flag" >&2
  exit 1
fi

echo "Built:"
file "$OUT/khromium-macos-intel" "$OUT/khromium-windows-x64.exe"
ls -lh "$OUT/khromium-macos-intel" "$OUT/khromium-windows-x64.exe"
