#!/bin/sh
# Build the Khromium desktop app for Intel macOS and 64-bit Windows.
# Requires Zig 0.14 or newer: https://ziglang.org/download/
# Override the compiler with ZIG=/path/to/zig if it is not on PATH.
#
# Windows: zig build-exe -target x86_64-windows-gnu --subsystem windows
# macOS:   zig build-exe -target x86_64-macos.10.13
# A full Mac SDK is not required. This script writes temporary .tbd stubs
# whose install names are the system AppKit, Foundation, and libobjc paths.

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

if ! python3 "$HERE/render_logo.py"; then
  echo "logo render failed; keeping the assets already in assets/." >&2
fi
test -f "$HERE/assets/logo.svg"
test -f "$HERE/assets/logo-256.png"
test -f "$HERE/assets/logo-32.png"
test -f "$HERE/assets/logo.ico"
test -f "$HERE/assets/AppIcon.icns"
test -f "$HERE/assets/AppIcon.png"

WIN="$OUT/khromium-windows-x64.exe"
EMBEDDED=0
if "$ZIG" build-exe "$HERE/src/main.zig" "$HERE/assets/khromium.rc" \
  -target x86_64-windows-gnu \
  --subsystem windows \
  -O ReleaseSmall \
  -luser32 -lgdi32 -lshell32 \
  --name khromium \
  -femit-bin="$WIN"
then
  EMBEDDED=1
else
  echo "Windows resource compile failed. Building a GUI exe without an embedded icon." >&2
  "$ZIG" build-exe "$HERE/src/main.zig" \
    -target x86_64-windows-gnu \
    --subsystem windows \
    -O ReleaseSmall \
    -luser32 -lgdi32 -lshell32 \
    --name khromium \
    -femit-bin="$WIN"
  cp "$HERE/assets/logo.ico" "$OUT/logo.ico"
fi
chmod 755 "$WIN"
rm -f "$WIN.obj" "$OUT/khromium.obj"

STUB=$(mktemp -d)
APP="$OUT/Khromium.app"
cleanup() {
  rm -rf "$STUB"
}
trap cleanup EXIT

mkdir -p "$STUB/System/Library/Frameworks/AppKit.framework" \
  "$STUB/System/Library/Frameworks/Foundation.framework" \
  "$STUB/usr/lib"

cat > "$STUB/System/Library/Frameworks/AppKit.framework/AppKit.tbd" <<'EOF'
--- !tapi-tbd
tbd-version:     4
targets:         [ x86_64-macos ]
uuids:
  - target:          x86_64-macos
    value:           11111111-1111-1111-1111-111111111111
install-name:    '/System/Library/Frameworks/AppKit.framework/Versions/C/AppKit'
current-version: 2560
compatibility-version: 45
exports:
  - targets:         [ x86_64-macos ]
    symbols:         [ _NSApplicationMain ]
...
EOF

cat > "$STUB/System/Library/Frameworks/Foundation.framework/Foundation.tbd" <<'EOF'
--- !tapi-tbd
tbd-version:     4
targets:         [ x86_64-macos ]
uuids:
  - target:          x86_64-macos
    value:           33333333-3333-3333-3333-333333333333
install-name:    '/System/Library/Frameworks/Foundation.framework/Versions/C/Foundation'
current-version: 3000
compatibility-version: 300
exports:
  - targets:         [ x86_64-macos ]
    symbols:         [ _NSLog ]
...
EOF

cat > "$STUB/usr/lib/libobjc.tbd" <<'EOF'
--- !tapi-tbd
tbd-version:     4
targets:         [ x86_64-macos ]
uuids:
  - target:          x86_64-macos
    value:           44444444-4444-4444-4444-444444444444
install-name:    '/usr/lib/libobjc.A.dylib'
current-version: 228
compatibility-version: 1
exports:
  - targets:         [ x86_64-macos ]
    symbols:         [ _objc_getClass, _objc_msgSend, _sel_registerName, _objc_allocateClassPair, _class_addMethod, _objc_registerClassPair ]
...
EOF

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
"$ZIG" build-exe "$HERE/src/main.zig" \
  -target x86_64-macos.10.13 \
  -O ReleaseSmall \
  -F "$STUB/System/Library/Frameworks" \
  -L "$STUB/usr/lib" \
  -needed_framework AppKit \
  -needed_framework Foundation \
  -lobjc \
  --name Khromium \
  -femit-bin="$APP/Contents/MacOS/Khromium"
chmod 755 "$APP/Contents/MacOS/Khromium"
rm -f "$APP/Contents/MacOS/Khromium.o"
cp "$HERE/macos/Info.plist" "$APP/Contents/Info.plist"
cp "$HERE/assets/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
cp "$HERE/assets/AppIcon.png" "$APP/Contents/Resources/AppIcon.png"
printf 'APPL????' > "$APP/Contents/PkgInfo"
# The old raw Mach-O download is replaced by the app zip.
rm -f "$OUT/khromium-macos-intel"

ZIP="$OUT/Khromium-mac-intel.zip"
python3 - "$APP" "$ZIP" <<'PY'
import os
import stat
import sys
import zipfile
from pathlib import Path

app = Path(sys.argv[1])
dest = Path(sys.argv[2])
if dest.exists():
    dest.unlink()
with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(p for p in app.rglob("*") if p.is_file()):
        rel = Path("Khromium.app") / path.relative_to(app)
        info = zipfile.ZipInfo(rel.as_posix())
        mode = path.stat().st_mode & 0o777
        info.external_attr = (stat.S_IFREG | mode) << 16
        info.create_system = 3
        archive.writestr(info, path.read_bytes())
print(f"wrote {dest}")
PY

EMBEDDED="$EMBEDDED" python3 - "$WIN" "$APP/Contents/MacOS/Khromium" "$ZIP" <<'PY'
import os
import struct
import sys
import zipfile

win_path, mac_path, zip_path = sys.argv[1:]
embedded = os.environ.get("EMBEDDED") == "1"
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
subsystem, = struct.unpack_from("<H", win, pe + 24 + 68)
if subsystem != 2:
    raise SystemExit(f"Windows binary subsystem is {subsystem}, expected WINDOWS (2)")
res_size, = struct.unpack_from("<I", win, pe + 24 + 112 + 16 + 4)
if embedded and res_size == 0:
    raise SystemExit("Windows binary has an empty resource directory")
if embedded:
    for label in ("ProductName", "FileDescription", "OriginalFilename", "Khromium", "khromium-windows-x64.exe"):
        if label.encode("utf-16le") not in win:
            raise SystemExit(f"Windows version resource is missing {label}")
    if b"\x89PNG" not in win:
        raise SystemExit("Windows binary does not contain the PNG icon")

mac = open(mac_path, "rb").read()
magic, cputype = struct.unpack_from("<II", mac, 0)
if magic != 0xFEEDFACF:
    raise SystemExit(f"macOS binary is not little-endian 64-bit Mach-O (magic {magic:#x})")
if cputype != 0x01000007:
    raise SystemExit(f"macOS binary is not x86_64 (cputype {cputype:#x})")
needles = (
    b"/System/Library/Frameworks/AppKit.framework/Versions/C/AppKit",
    b"/System/Library/Frameworks/Foundation.framework/Versions/C/Foundation",
    b"/usr/lib/libobjc.A.dylib",
)
for needle in needles:
    if needle not in mac:
        raise SystemExit(f"macOS binary is not linked to {needle.decode()}")
if b"/tmp/" in mac:
    raise SystemExit("macOS binary contains a temporary stub path")
def has_phrase(blob: bytes, phrase: str) -> bool:
    return phrase.encode("utf-8") in blob or phrase.encode("utf-16le") in blob

for phrase in ("Khromium", "30 days", "twice the API cost", "http://127.0.0.1:8787"):
    if not has_phrase(mac, phrase) or not has_phrase(win, phrase):
        raise SystemExit(f"missing phrase {phrase!r}")
for secret in (b"sk_live_", b"sk_test_", b"whsec_", b"rk_live_"):
    if secret in mac or secret in win:
        raise SystemExit(f"binary contains {secret!r}")

with zipfile.ZipFile(zip_path) as archive:
    names = set(archive.namelist())
    required = {
        "Khromium.app/Contents/Info.plist",
        "Khromium.app/Contents/PkgInfo",
        "Khromium.app/Contents/MacOS/Khromium",
        "Khromium.app/Contents/Resources/AppIcon.icns",
        "Khromium.app/Contents/Resources/AppIcon.png",
    }
    missing = required - names
    if missing:
        raise SystemExit(f"zip is missing {sorted(missing)}")
    packed = archive.read("Khromium.app/Contents/MacOS/Khromium")
    if packed != mac:
        raise SystemExit("zip Mach-O does not match the app executable")
    plist = archive.read("Khromium.app/Contents/Info.plist")
    if b"Khromium" not in plist or b"AppIcon" not in plist:
        raise SystemExit("Info.plist is missing the executable or icon name")
    if not archive.read("Khromium.app/Contents/Resources/AppIcon.icns").startswith(b"icns"):
        raise SystemExit("AppIcon.icns does not start with the icns magic")
print("desktop app headers, icon, version resource, and zip ok")
PY

HOST=$(mktemp -d)
trap 'rm -rf "$STUB" "$HOST"' EXIT
"$ZIG" build-exe "$HERE/src/main.zig" -O ReleaseSmall -femit-bin="$HOST/khromium-host"
"$HOST/khromium-host" --self-check >"$HOST/out"
grep -F -q 'Khromium' "$HOST/out"
grep -F -q '30 days' "$HOST/out"
grep -F -q 'twice the API cost' "$HOST/out"
grep -F -q 'model key' "$HOST/out"
grep -F -q 'http://127.0.0.1:8787' "$HOST/out"
if grep -E -q 'sk_live_|sk_test_|whsec_|rk_live_' "$HOST/out"; then
  echo "self-check output contains a secret-shaped token" >&2
  exit 1
fi

echo "Built:"
file "$APP/Contents/MacOS/Khromium" "$WIN"
ls -lh "$APP/Contents/MacOS/Khromium" "$WIN" "$ZIP"
