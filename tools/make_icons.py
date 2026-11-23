#!/usr/bin/env python3
"""Draw the Mam-IA logo: the SVG used by the pages and the PNG icons (PWA, Apple, favicon, Play Store).

The logo is a heart (the family) with a small spark (the assistant) on a rounded square in the accent colour. Both the
SVG and the PNGs come from the same curves, so they always match. Needs Pillow (`pip install -e ".[dev]"`).

Usage: python tools/make_icons.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "branding"   # served at the root of the site: /logo.svg, /icon-192.png…
TOP, BOTTOM = (0xE0, 0x5A, 0x82), (0xB2, 0x2F, 0x58)     # the background gradient (accent colour)
HEART = (0xFF, 0xFF, 0xFF)
SPARK = (0xFF, 0xE3, 0x9B)


def heart_points(cx: float, cy: float, size: float, n: int = 180) -> list[tuple[float, float]]:
    """The classic heart curve, `size` wide, centred on (cx, cy)."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x, y))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    k = size / w
    mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return [(cx + (x - mx) * k, cy + (y - my) * k) for x, y in pts]


def spark_points(cx: float, cy: float, r: float, n: int = 96) -> list[tuple[float, float]]:
    """A four-pointed spark (astroid)."""
    return [(cx + r * math.cos(t) ** 3, cy + r * math.sin(t) ** 3)
            for t in (2 * math.pi * i / n for i in range(n))]


def shapes(s: float) -> tuple[list, list]:
    """Heart and spark for a canvas of side s (the content fills about 60 % of it, inside the maskable safe zone)."""
    return heart_points(s * 0.46, s * 0.555, s * 0.52), spark_points(s * 0.765, s * 0.245, s * 0.105)


def svg() -> str:
    s = 512
    heart, spark = shapes(s)
    path = lambda pts: "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"   # noqa: E731
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}" role="img" aria-label="Mam-IA">\n'
            '  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#{"".join(f"{c:02X}" for c in TOP)}"/>'
            f'<stop offset="1" stop-color="#{"".join(f"{c:02X}" for c in BOTTOM)}"/></linearGradient></defs>\n'
            f'  <rect width="{s}" height="{s}" rx="{s * 0.23:.0f}" fill="url(#g)"/>\n'
            f'  <path fill="#FFFFFF" d="{path(heart)}"/>\n'
            f'  <path fill="#{"".join(f"{c:02X}" for c in SPARK)}" d="{path(spark)}"/>\n'
            '</svg>\n')


def png(size: int, *, rounded: bool, pad: float = 0.0) -> Image.Image:
    """The icon at `size` pixels (drawn 4× larger and reduced, for smooth edges). `pad` leaves a transparent margin."""
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    grad = Image.new("RGBA", (big, big))
    gd = ImageDraw.Draw(grad)
    for y in range(big):
        k = y / (big - 1)
        gd.line([(0, y), (big, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(TOP, BOTTOM)) + (255,))
    inner = round(big * (1 - 2 * pad))
    off = (big - inner) // 2
    mask = Image.new("L", (big, big), 0)
    md = ImageDraw.Draw(mask)
    if rounded:
        md.rounded_rectangle([off, off, off + inner - 1, off + inner - 1], radius=round(inner * 0.23), fill=255)
    else:
        md.rectangle([off, off, off + inner - 1, off + inner - 1], fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    heart, spark = shapes(inner)
    d.polygon([(x + off, y + off) for x, y in heart], fill=HEART + (255,))
    d.polygon([(x + off, y + off) for x, y in spark], fill=SPARK + (255,))
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    icons = OUT
    icons.mkdir(parents=True, exist_ok=True)
    (OUT / "logo.svg").write_text(svg(), encoding="utf-8")
    png(192, rounded=True).save(icons / "icon-192.png")
    png(512, rounded=True).save(icons / "icon-512.png")
    png(512, rounded=False).save(icons / "icon-maskable-512.png")       # full bleed: Android crops it to its shape
    png(180, rounded=False).convert("RGB").save(icons / "apple-touch-icon.png")   # iOS rounds the corners itself
    png(32, rounded=True).save(icons / "favicon-32.png")
    print("Logo and icons written to", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
