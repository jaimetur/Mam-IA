"""Pages and static files: the landing page, the app, the account and legal pages, the PWA files and the APK."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from app.core import config, i18n, version
from app.core.deps import optional_user

router = APIRouter()
APP_UA = "MamIAApp/"
# the slim Docker image has no system table of file types: the ones the pages use, always right
for _type, _ext in (("font/woff2", ".woff2"), ("image/svg+xml", ".svg"), ("text/javascript", ".js"), ("text/css", ".css"),
                    ("application/manifest+json", ".webmanifest"), ("image/png", ".png")):
    mimetypes.add_type(_type, _ext)


def _front(*parts: str) -> Path:
    return config.settings.frontend_dir.joinpath(*parts)


def _html(request: Request, *parts: str, **extra: str) -> HTMLResponse:
    """A page with its own static files marked with the version (browsers never use an old copy), in the language of
    the person (its dictionary and lang/i18n.js go first in the head, so every text is translated as it appears)."""
    html = _front(*parts).read_text(encoding="utf-8").replace("{{v}}", version.stamp())
    for k, v in extra.items():
        html = html.replace("{{" + k + "}}", v)
    lang = i18n.request_lang(request, optional_user(request))
    html = re.sub(r"(<head[^>]*>)", lambda m: m.group(1) + i18n.head(lang), html, count=1)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache", "Content-Language": lang, "Vary": "Cookie, Accept-Language"})


def _next(request: Request) -> str:
    """Where to go after signing in: the page asked for, with its query (shared text, a reminder done…)."""
    q = request.url.query
    return quote(request.url.path + (f"?{q}" if q else ""), safe="")


@router.get("/")
def index(request: Request):
    u = optional_user(request)
    if u:
        return RedirectResponse("/app", status_code=303)
    if APP_UA in request.headers.get("user-agent", ""):   # the Android app goes straight to signing in
        return RedirectResponse("/entrar", status_code=303)
    return _html(request, "landing", "index.html")


@router.get("/app")
def app_page(request: Request):
    u = optional_user(request)
    if not u:
        return RedirectResponse(f"/entrar?next={_next(request)}", status_code=303)
    if u.must_change:
        return RedirectResponse("/cuenta?cambiar=1", status_code=303)
    return _html(request, "app", "index.html")


def _account_page(name: str, signed_in: bool = False):
    def page(request: Request):
        if signed_in and not optional_user(request):
            return RedirectResponse(f"/entrar?next={_next(request)}", status_code=303)
        return _html(request, "accounts", f"{name}.html")
    return page


for _path, _name, _auth in (("/entrar", "entrar", False), ("/alta", "alta", False), ("/bienvenida", "bienvenida", False),
                            ("/unirse", "unirse", False), ("/recuperar", "recuperar", False), ("/cuenta", "cuenta", True)):
    router.add_api_route(_path, _account_page(_name, _auth), methods=["GET"], include_in_schema=False)


@router.get("/admin")
def admin_page(request: Request):
    u = optional_user(request)
    if not u:
        return RedirectResponse(f"/entrar?next={_next(request)}", status_code=303)
    if not u.is_admin:
        return RedirectResponse("/app", status_code=303)
    return _html(request, "admin", "admin.html")


def _legal_page(name: str):
    def page(request: Request):
        return _html(request, "legal", f"{name}.html")
    return page


for _path, _name in (("/privacidad", "privacidad"), ("/terminos", "terminos"), ("/borrar-cuenta", "borrar-cuenta")):
    router.add_api_route(_path, _legal_page(_name), methods=["GET"],
                         include_in_schema=False)


@router.get("/lang/i18n.js")
def lang_translator():
    return FileResponse(config.settings.lang_dir / "i18n.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@router.get("/lang/{code}.js")
def lang_dictionary(code: str):
    if code not in i18n.LANGS:
        raise HTTPException(404)
    return Response(i18n.script(code), media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@router.get("/manifest.webmanifest")
def manifest():
    return FileResponse(_front("app", "manifest.webmanifest"), media_type="application/manifest+json",
                        headers={"Cache-Control": "no-cache"})


@router.get("/sw.js")
def service_worker():
    # served from the root so it can look after /app and the static files; the version makes every release a new one
    js = _front("app", "sw.js").read_text(encoding="utf-8").replace("{{v}}", version.stamp())
    return Response(js, media_type="text/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


RETIRED_SW = """// The service worker of the first Mam-IA kept the old app in its cache for ever: this one replaces it, deletes that
// cache, unregisters itself and reloads the open pages, so they get the new app.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil((async () => {
  for (const k of await caches.keys()) if (k === "mam-ia-v1" || k === "mam-ia-v0.1.0") await caches.delete(k);
  await self.registration.unregister();
  for (const c of await self.clients.matchAll({ type: "window" })) c.navigate(c.url);
})()));
"""


@router.get("/service-worker.js")
def retired_service_worker():
    return Response(RETIRED_SW, media_type="text/javascript", headers={"Cache-Control": "no-cache"})


# the brand's logo and icons (assets/branding in the repository, as in BodyLens), at the root of the site
BRANDING = ("logo.svg", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-512.png")


def _branding(name: str):
    def serve():
        return FileResponse(config.settings.branding_dir / name, headers={"Cache-Control": "public, max-age=86400"})
    return serve


for _name in BRANDING:
    router.add_api_route(f"/{_name}", _branding(_name), methods=["GET"], include_in_schema=False)


@router.get("/favicon.ico")
def favicon():
    return FileResponse(config.settings.branding_dir / "favicon-32.png", media_type="image/png")


@router.get("/android.apk")
def android_apk():
    apk = config.settings.data_dir / "android" / "mamia-android.apk"
    if apk.is_file():
        return FileResponse(apk, media_type="application/vnd.android.package-archive", filename="mamia-android.apk")
    return RedirectResponse(config.settings.android_url, status_code=302)


@router.get("/static/{path:path}")
def static(path: str):
    root = config.settings.frontend_dir.resolve()
    f = (root / path).resolve()
    if root not in f.parents or not f.is_file() or f.suffix == ".html":
        raise HTTPException(404)
    # every page asks for its files with ?v=<version>: they are checked again each time but rarely downloaded twice
    return FileResponse(f, headers={"Cache-Control": "no-cache"})
