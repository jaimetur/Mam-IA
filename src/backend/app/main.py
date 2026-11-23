"""Mam-IA server (FastAPI): start-up, common security and the routes of each module."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.accounts import routes as accounts_routes
from app.admin import routes as admin_routes
from app.billing import codes
from app.billing import web as billing_web
from app.core import backup, config, db, version
from app.core.deps import CSRF_HEADER
from app.data import routes as data_routes
from app.families import routes as families_routes
from app.families import service as families
from app.push import routes as push_routes
from app.web import routes as web_routes

log = logging.getLogger("mamia")


class _HideSecrets(logging.Filter):
    """The access log never shows the tokens in URLs (invitations, password resets, Stripe sessions)."""
    _RX = re.compile(r"([?&](?:c|t|token|session_id)=)[^&\s\"]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(self._RX.sub(r"\1***", a) if isinstance(a, str) else a for a in record.args)
        return True


logging.getLogger("uvicorn.access").addFilter(_HideSecrets())


def bootstrap_admin() -> None:
    """With an empty database, the server administrator's account (and family) from MAMIA_ADMIN_EMAIL; the password
    has to be changed on entering. The administrator's family is free for life."""
    s = config.settings
    if not s.admin_email:
        return
    with db.tx() as con:
        if con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return
        u = families.create_family(con, s.admin_family, s.admin_name, s.admin_email, s.admin_password,
                                   is_admin=True, must_change=True)
        codes.grant(con, u.family_id, "admin", None)
    log.warning("Created the administration account %s with the temporary password from MAMIA_ADMIN_PASSWORD: "
                "change it on entering.", s.admin_email)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    bootstrap_admin()
    tasks = []
    if config.settings.scheduler_enabled:
        tasks = [asyncio.create_task(backup.loop()), asyncio.create_task(push_routes.loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Mam-IA", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path
    # against CSRF: every write to the API carries a header of its own (another site's form cannot set it);
    # Stripe's webhook is checked by its signature instead
    if path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS") \
            and path != "/api/web/webhook" and request.headers.get(CSRF_HEADER) != "1":
        return JSONResponse({"detail": "Falta la cabecera de la app."}, status_code=403)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.get("/api/version")
def api_version():
    return version.current()


@app.get("/healthz")
def healthz():
    with db.ro() as con:
        con.execute("SELECT 1").fetchone()
    return {"ok": True}


# the order matters: the pages and static files go last
for r in (accounts_routes.router, families_routes.router, data_routes.router, push_routes.router, billing_web.router,
          admin_routes.router, web_routes.router):
    app.include_router(r)
