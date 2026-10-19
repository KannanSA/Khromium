#!/usr/bin/env python3
# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.
"""Rasterize the Khromium mark: a flat geometric K on an ocean rounded square.

The SVG in assets/logo.svg is the source. This script redraws the same
polygons so the PNG, ICO, and ICNS files match it. Requires numpy.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"

# 256-unit design space. y grows downward, matching SVG.
NAVY = (8, 36, 63, 255)  # #08243F
TEAL = (30, 212, 198, 255)  # #1ED4C6
SEA = (58, 160, 255, 255)  # #3AA0FF
FOAM = (245, 251, 255, 255)  # #F5FBFF
RADIUS = 58.0


def thick_segment(x1: float, y1: float, x2: float, y2: float, thickness: float) -> list[tuple[float, float]]:
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    px = -dy / length * (thickness / 2.0)
    py = dx / length * (thickness / 2.0)
    return [
        (x1 + px, y1 + py),
        (x2 + px, y2 + py),
        (x2 - px, y2 - py),
        (x1 - px, y1 - py),
    ]


# Stem is foam and is painted last so the joint stays solid.
# Inner ends sit under the stem. Outer ends stay inside the rounded square.
UPPER_ARM = thick_segment(78, 134, 186, 54, 52)
LOWER_ARM = thick_segment(78, 122, 186, 202, 52)
STEM = [(50, 40), (114, 40), (114, 216), (50, 216)]


def rounded_mask(x: np.ndarray, y: np.ndarray, size: float, radius: float) -> np.ndarray:
    half = size / 2.0
    qx = np.abs(x - half) - (half - radius)
    qy = np.abs(y - half) - (half - radius)
    outside = np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2)
    inside = np.minimum(np.maximum(qx, qy), 0.0)
    return (outside + inside) <= radius


def fill_polygon(mask_target: np.ndarray, x: np.ndarray, y: np.ndarray, points: list[tuple[float, float]]) -> None:
    pts = np.asarray(points, dtype=np.float64)
    x0 = pts[:, 0]
    y0 = pts[:, 1]
    x1 = np.roll(x0, -1)
    y1 = np.roll(y0, -1)
    xf = x[..., None]
    yf = y[..., None]
    dy = y1 - y0
    dy = np.where(np.abs(dy) < 1e-9, 1e-9, dy)
    crosses = ((y0 > yf) != (y1 > yf)) & (xf < (x1 - x0) * (yf - y0) / dy + x0)
    inside = np.count_nonzero(crosses, axis=-1) % 2 == 1
    mask_target[inside] = True


def render(size: int, samples: int = 4) -> np.ndarray:
    big = size * samples
    scale = big / 256.0
    ys, xs = np.mgrid[0:big, 0:big]
    x = (xs + 0.5) / scale
    y = (ys + 0.5) / scale
    color = np.zeros((big, big, 4), dtype=np.uint8)
    tile = rounded_mask(x, y, 256.0, RADIUS)
    color[tile] = NAVY
    arm_upper = np.zeros((big, big), dtype=bool)
    arm_lower = np.zeros((big, big), dtype=bool)
    stem = np.zeros((big, big), dtype=bool)
    fill_polygon(arm_upper, x, y, UPPER_ARM)
    fill_polygon(arm_lower, x, y, LOWER_ARM)
    fill_polygon(stem, x, y, STEM)
    color[arm_upper & tile] = TEAL
    color[arm_lower & tile] = SEA
    color[stem & tile] = FOAM

    rgb = color[..., :3].astype(np.float32)
    alpha = color[..., 3:4].astype(np.float32) / 255.0
    premultiplied = rgb * alpha
    premultiplied = premultiplied.reshape(size, samples, size, samples, 3).mean(axis=(1, 3))
    alpha_out = alpha.reshape(size, samples, size, samples, 1).mean(axis=(1, 3))
    safe = np.maximum(alpha_out, 1e-6)
    out_rgb = np.clip(premultiplied / safe, 0, 255)
    out = np.concatenate([out_rgb, alpha_out * 255.0], axis=-1)
    return out.astype(np.uint8)


def png_bytes(image: np.ndarray) -> bytes:
    height, width, channels = image.shape
    if channels != 4:
        raise SystemExit("expected RGBA")
    raw = b"".join(b"\x00" + image[y].tobytes() for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def write_png(path: Path, image: np.ndarray) -> None:
    path.write_bytes(png_bytes(image))


def write_ico(path: Path, images: list[tuple[int, np.ndarray]]) -> None:
    blobs = [(size, png_bytes(image)) for size, image in images]
    count = len(blobs)
    header = struct.pack("<HHH", 0, 1, count)
    entries = b""
    payload = b""
    offset = 6 + 16 * count
    for size, blob in blobs:
        entries += struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,
            size if size < 256 else 0,
            0,
            0,
            1,
            32,
            len(blob),
            offset,
        )
        offset += len(blob)
        payload += blob
    path.write_bytes(header + entries + payload)


def write_icns(path: Path, chunks: list[tuple[bytes, np.ndarray]]) -> None:
    body = b""
    for kind, image in chunks:
        blob = png_bytes(image)
        body += kind + struct.pack(">I", 8 + len(blob)) + blob
    path.write_bytes(b"icns" + struct.pack(">I", 8 + len(body)) + body)


def svg_points(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def write_svg(path: Path) -> None:
    text = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256" role="img" aria-label="Khromium">
  <title>Khromium</title>
  <rect width="256" height="256" rx="{RADIUS:.0f}" fill="#08243F"/>
  <polygon points="{svg_points(UPPER_ARM)}" fill="#1ED4C6"/>
  <polygon points="{svg_points(LOWER_ARM)}" fill="#3AA0FF"/>
  <polygon points="{svg_points(STEM)}" fill="#F5FBFF"/>
</svg>
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    write_svg(ASSETS / "logo.svg")
    cache: dict[int, np.ndarray] = {}

    def image(size: int) -> np.ndarray:
        if size not in cache:
            samples = 8 if size <= 32 else 4
            cache[size] = render(size, samples)
        return cache[size]

    write_png(ASSETS / "logo-256.png", image(256))
    write_png(ASSETS / "logo-32.png", image(32))
    write_png(ASSETS / "AppIcon.png", image(512))
    write_ico(
        ASSETS / "logo.ico",
        [(16, image(16)), (32, image(32)), (48, image(48)), (256, image(256))],
    )
    write_icns(
        ASSETS / "AppIcon.icns",
        [
            (b"icp4", image(16)),
            (b"icp5", image(32)),
            (b"ic11", image(32)),
            (b"icp6", image(64)),
            (b"ic12", image(64)),
            (b"ic07", image(128)),
            (b"ic08", image(256)),
            (b"ic13", image(256)),
            (b"ic09", image(512)),
            (b"ic14", image(512)),
        ],
    )
    print(f"wrote logo assets in {ASSETS}")


if __name__ == "__main__":
    main()
