#!/usr/bin/env python3
"""Make the Google Play store images of Mam-IA in every language of the app: phone, tablet and Chromebook screenshots
and the feature graphic, from the app itself filled with the made-up family of app.demo.play_review.

Google Play shows each visitor the screenshots of the listing translation in their language, so every language has its
own folder, named with Play's language code:

    assets/play-store/icon-512.png
    assets/play-store/<es-ES|en-US|ca|fr-FR|it-IT|de-DE|pt-PT|nl-NL|zh-CN|ja-JP>/
        feature-graphic.png              1024x500
        phone/01-hoy.png …               1080x1920 (9:16)
        tablet/01-hoy.png …              1440x2560 (9:16), the same for 7" and 10" tablets
        chromebook/01-hoy.png …          2880x1620 (16:9)

It starts the server on a free local port with a throwaway database (nothing is sent anywhere), signs in to the demo
family and photographs each screen with the interface and the family's texts in each language. The dates are fixed
(the week of 23 November 2026, a Wednesday morning) and the animations are off. Even so, two runs do not draw exactly
the same pixels (anti-aliasing of the fonts), so an image is only rewritten when it really changes: more than
CHANGED_PIXELS pixels differ by more than PIXEL_TOLERANCE (keep()). Without it, every run committed dozens of images
that look the same, and each one went to Google Play's review again.

Needs Pillow and Playwright: pip install -e ".[dev]" && python -m playwright install chromium
(locally you can use an installed Edge or Chrome instead: --channel msedge).

Usage: python tools/play_screenshots.py [--lang es en …] [--device phone tablet chromebook] [--channel msedge]
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "play-store"
BACKEND = ROOT / "src" / "backend"

# the app's languages and Google Play's code for each listing translation
LOCALES = {"es": "es-ES", "en": "en-US", "ca": "ca", "fr": "fr-FR", "it": "it-IT", "de": "de-DE", "pt": "pt-PT",
           "nl": "nl-NL", "zh": "zh-CN", "ja": "ja-JP"}
BROWSER_LOCALE = {"es": "es-ES", "en": "en-US", "ca": "ca-ES", "fr": "fr-FR", "it": "it-IT", "de": "de-DE",
                  "pt": "pt-PT", "nl": "nl-NL", "zh": "zh-CN", "ja": "ja-JP"}
# viewport (CSS px), pixel ratio and touch: the file sizes are viewport x ratio
DEVICES = {"phone": (360, 640, 3, True), "tablet": (720, 1280, 2, True), "chromebook": (1440, 810, 2, False)}
VIEWS = ["hoy", "agenda", "tareas", "compras", "menu", "reparto"]
TODAY = date(2026, 11, 24)                    # the demo data is laid out around this day…
CLOCK = "2026-11-25T08:30:00+01:00"           # …and the app is photographed the next morning
EMAIL = "demo@mamia.test"

# the feature graphic: the brand line and the four things the app does
TAGLINE = {
    "es": ("El cerebro compartido de tu familia", "Agenda · Tareas · Compra · Menú"),
    "en": ("Your family's shared brain", "Calendar · Tasks · Shopping · Menu"),
    "ca": ("El cervell compartit de la teva família", "Agenda · Tasques · Compra · Menú"),
    "fr": ("Le cerveau partagé de votre famille", "Agenda · Tâches · Courses · Menu"),
    "it": ("Il cervello condiviso della tua famiglia", "Agenda · Attività · Spesa · Menù"),
    "de": ("Das gemeinsame Gedächtnis deiner Familie", "Kalender · Aufgaben · Einkauf · Essensplan"),
    "pt": ("O cérebro partilhado da tua família", "Agenda · Tarefas · Compras · Menu"),
    "nl": ("Het gedeelde brein van je gezin", "Agenda · Taken · Boodschappen · Menu"),
    "zh": ("全家共享的大脑", "日程 · 任务 · 购物 · 菜单"),
    "ja": ("家族みんなの共有ブレーン", "予定 · タスク · 買い物 · 献立"),
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(data_dir: Path, port: int) -> subprocess.Popen:
    env = {**os.environ, "DATA_DIR": str(data_dir), "COOKIE_SECURE": "0", "SMTP_HOST": "log", "SCHEDULER_ENABLED": "0",
           "MAMIA_ADMIN_EMAIL": "admin@mamia.test", "MAMIA_ADMIN_PASSWORD": secrets.token_urlsafe(16),
           "PYTHONPATH": str(BACKEND), "TZ": "Europe/Madrid"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
                             "--log-level", "warning"], cwd=ROOT, env=env)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=1)
            return proc
        except OSError:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit("The server did not start.")


def fill(data_dir: Path, lang: str, password: str | None) -> None:
    """Write the demo family with its texts in `lang` (in a child process: the app reads DATA_DIR when imported)."""
    code = ("import sys; from datetime import date; from app.demo import play_review as p; "
            f"p.fill({EMAIL!r}, sys.argv[1] or None, {lang!r}, date({TODAY.year}, {TODAY.month}, {TODAY.day}))")
    env = {**os.environ, "DATA_DIR": str(data_dir), "PYTHONPATH": str(BACKEND), "SMTP_HOST": "log"}
    subprocess.run([sys.executable, "-c", code, password or ""], cwd=ROOT, env=env, check=True)
    # on the screenshots the names read as a real family, without the "(demo)" marks
    con = sqlite3.connect(next(data_dir.glob("*.db")))
    con.execute("UPDATE families SET name = 'Martín'")
    con.execute("UPDATE users SET name = 'Sam' WHERE email LIKE 'sam@%'")
    con.commit()
    con.close()


PIXEL_TOLERANCE = 48   # a difference of a pixel (0-255, the largest of its channels) that is only rendering noise
CHANGED_PIXELS = 50    # an image with more pixels than this differing more than PIXEL_TOLERANCE has changed


def same_image(old, new) -> bool:
    """The two images look the same: same size and at most CHANGED_PIXELS pixels differ more than PIXEL_TOLERANCE.
    (Measured on the images of 25 November 2026: the noise between runs is a few pixels differing by 2-37; a changed
    word is thousands of pixels differing by more than 100.)"""
    from PIL import ImageChops
    if old.size != new.size:
        return False
    hist = ImageChops.difference(old.convert("RGB"), new.convert("RGB")).convert("L").histogram()
    return sum(hist[PIXEL_TOLERANCE + 1:]) <= CHANGED_PIXELS


def keep(path: Path, png: bytes) -> bool:
    """Save a screenshot as Play wants it (RGB, no transparency), unless the image already there looks the same: then
    the file is not touched. True if it was written."""
    from PIL import Image
    new = Image.open(io.BytesIO(png)).convert("RGB")
    if path.exists():
        try:
            if same_image(Image.open(path), new):
                return False
        except OSError:
            pass
    new.save(path, format="PNG", optimize=True)
    return True


def shoot(pw, channel: str | None, base: str, password: str, lang: str, device: str) -> None:
    w, h, ratio, touch = DEVICES[device]
    out = OUT / LOCALES[lang] / device
    out.mkdir(parents=True, exist_ok=True)
    browser = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=ratio, is_mobile=touch,
                              has_touch=touch, locale=BROWSER_LOCALE[lang], timezone_id="Europe/Madrid",
                              color_scheme="light", reduced_motion="reduce")
    ctx.add_cookies([{"name": "mamia_lang", "value": lang, "url": base}])
    page = ctx.new_page()
    page.clock.install(time=CLOCK)
    head = {"x-mamia": "1"}
    r = page.request.post(f"{base}/api/login", data={"email": EMAIL, "password": password}, headers=head)
    if not r.ok:
        raise SystemExit(f"Could not sign in to the demo family: {r.text()}")
    page.request.put(f"{base}/api/me", data={"lang": lang}, headers=head)
    for i, view in enumerate(VIEWS, 1):
        page.goto(f"{base}/app#{view}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(900)
        path = out / f"{i:02d}-{view}.png"
        print(f"  {path.relative_to(ROOT)}: {'changed' if keep(path, page.screenshot(animations='disabled', caret='hide')) else 'the same'}")
    browser.close()


def feature_graphic(pw, channel: str | None, lang: str) -> None:
    title, sub = TAGLINE[lang]
    folder = OUT / LOCALES[lang]
    logo = (ROOT / "assets" / "branding" / "logo.svg").read_text(encoding="utf-8")

    def data_uri(p: Path) -> str:
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()

    a, b = data_uri(folder / "phone" / "01-hoy.png"), data_uri(folder / "phone" / "02-agenda.png")
    small = len(title) > 32 or (lang in ("zh", "ja") and len(title) > 10)   # one line for Chinese and Japanese
    doc = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;800&display=block" rel="stylesheet">
<style>
*{{margin:0;box-sizing:border-box}}
body{{width:1024px;height:500px;overflow:hidden;font-family:"Bricolage Grotesque","Avenir Next","Noto Sans CJK SC","Noto Sans CJK JP",sans-serif;
 background:radial-gradient(circle at 15% 20%,#FBE4EB 0,transparent 45%),radial-gradient(circle at 70% 110%,#ECE6FB 0,transparent 50%),#F6F3F6;color:#231B29;position:relative}}
.l{{position:absolute;left:60px;top:0;bottom:0;width:520px;display:flex;flex-direction:column;justify-content:center;gap:18px}}
.brand{{display:flex;align-items:center;gap:16px;font-weight:800;font-size:64px;letter-spacing:-.03em}}
.brand svg{{width:84px;height:84px}}
h1{{font-size:{38 if small else 46}px;line-height:1.08;font-weight:800;letter-spacing:-.02em;color:#C93E66}}
p{{font-size:22px;font-weight:600;color:#5B4F63}}
.ph{{position:absolute;width:214px;border-radius:28px;border:7px solid #231B29;box-shadow:0 24px 50px rgba(35,27,41,.28);overflow:hidden;background:#fff}}
.ph img{{width:100%;display:block}}
.p1{{left:598px;top:46px;transform:rotate(-6deg)}}
.p2{{left:778px;top:84px;transform:rotate(5deg)}}
</style></head><body>
<div class="l"><div class="brand">{logo}Mam-IA</div><h1>{title}</h1><p>{sub}</p></div>
<div class="ph p1"><img src="{a}"></div><div class="ph p2"><img src="{b}"></div>
</body></html>"""
    browser = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1024, "height": 500})
    page.set_content(doc, wait_until="networkidle")
    page.wait_for_timeout(400)
    path = folder / "feature-graphic.png"
    png = page.screenshot(animations="disabled", caret="hide")
    browser.close()
    print(f"  {path.relative_to(ROOT)}: {'changed' if keep(path, png) else 'the same'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Google Play images of Mam-IA in every language.")
    ap.add_argument("--lang", nargs="+", choices=list(LOCALES), default=list(LOCALES))
    ap.add_argument("--device", nargs="+", choices=list(DEVICES), default=list(DEVICES))
    ap.add_argument("--channel", help="use an installed browser (msedge, chrome) instead of Playwright's Chromium")
    args = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit('Needs Playwright: pip install -e ".[dev]" && python -m playwright install chromium')

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon-512.png").write_bytes((ROOT / "assets" / "branding" / "icon-maskable-512.png").read_bytes())
    password = secrets.token_urlsafe(16)
    with tempfile.TemporaryDirectory(prefix="mamia-shots-") as tmp:
        data_dir = Path(tmp)
        first = True
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        server = None
        try:
            with sync_playwright() as pw:
                for lang in args.lang:
                    fill(data_dir, lang, password if first else None)
                    if first:
                        server = start_server(data_dir, port)
                        first = False
                    for device in args.device:
                        shoot(pw, args.channel, base, password, lang, device)
                        print(f"{LOCALES[lang]:6} {device}")
                    if "phone" in args.device:
                        feature_graphic(pw, args.channel, lang)
                        print(f"{LOCALES[lang]:6} feature graphic")
        finally:
            if server:
                server.terminate()
                server.wait(timeout=10)
    print(f"Done: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
