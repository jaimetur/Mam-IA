"""Email settings: the one-click link of the emails that turns them off, and Administración → Correo (the SMTP server
and a test email), as in BodyLens."""
from __future__ import annotations

import asyncio
from html import escape as esc

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.accounts import users
from app.accounts.users import User, UserError
from app.core import crypto, db, mailer
from app.core.deps import admin_user, base_url

router = APIRouter()
KINDS = {"recordatorios": ("mail_reminders", "los recordatorios por correo"),
         "resumen": ("mail_digest", "el resumen del día por correo")}


def _page(title: str, text: str) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, '
        'initial-scale=1, maximum-scale=1"><title>Mam-IA</title><link rel="stylesheet" href="/static/common/tokens.css">'
        '<link rel="stylesheet" href="/static/common/pages.css"></head><body><header class="top"><a class="brand" href="/">'
        '<img src="/logo.svg" width="32" height="32" alt="">Mam-IA</a></header><main class="wrap">'
        f'<section class="panel"><h1>{esc(title)}</h1><p class="lead">{text}</p>'
        '<a class="btn pri" href="/app#ajustes">Abrir los ajustes de Mam-IA</a></section></main></body></html>',
        headers={"Cache-Control": "no-store"})


def _unsubscribe(u: str, t: str, s: str) -> tuple[bool, str]:
    if t not in KINDS or not u.isdigit() or not crypto.signed(f"{u}:{t}", s):
        return False, ""
    column, what = KINDS[t]
    with db.tx() as con:
        con.execute(f"UPDATE users SET {column}=0 WHERE id=?", (int(u),))
    return True, what


@router.get("/correo/baja", include_in_schema=False)
def unsubscribe_page(u: str = "", t: str = "", s: str = ""):
    ok, what = _unsubscribe(u, t, s)
    if not ok:
        return _page("Enlace no válido", "Este enlace no es válido. Puedes elegir qué correos recibir en Mam-IA, en Ajustes.")
    return _page("Hecho", f"Ya no te enviaremos {esc(what)}. Si cambias de idea, vuelve a activarlo en Ajustes.")


@router.post("/correo/baja", include_in_schema=False)
def unsubscribe_one_click(u: str = "", t: str = "", s: str = ""):
    """The "unsubscribe" button of the email apps (RFC 8058): a POST to the same address."""
    ok, _ = _unsubscribe(u, t, s)
    if not ok:
        raise HTTPException(400, "Enlace no válido.")
    return {"ok": True}


# ---------- Administración → Correo ----------

class MailIn(BaseModel):
    host: str = ""
    port: int = 465
    security: str = "ssl"
    username: str = ""
    password: str = ""        # empty = keep the stored one
    from_address: str = ""
    from_name: str = "Mam-IA"
    remove: bool = False      # forget what was saved here (the .env applies again)


@router.get("/api/admin/mail")
def get_mail(u: User = Depends(admin_user)):
    return mailer.public_settings()


@router.put("/api/admin/mail")
def put_mail(body: MailIn, u: User = Depends(admin_user)):
    if body.remove:
        with db.tx() as con:
            db.set_setting(con, "mail", {})
        return mailer.public_settings()
    if body.security not in ("ssl", "starttls", "none"):
        raise HTTPException(400, "Seguridad: ssl, starttls o none.")
    if not 1 <= body.port <= 65535:
        raise HTTPException(400, "El puerto no es válido.")
    try:
        if body.from_address.strip():
            users.clean_email(body.from_address)
    except UserError:
        raise HTTPException(400, "El remitente no es un correo válido.")
    stored = db.get_setting("mail", {}) or {}
    new = {"host": body.host.strip(), "port": body.port, "security": body.security, "username": body.username.strip(),
           "from_address": body.from_address.strip(), "from_name": body.from_name.strip() or "Mam-IA",
           "password": crypto.encrypt(body.password) if body.password else stored.get("password", "")}
    with db.tx() as con:
        db.set_setting(con, "mail", new)
    return mailer.public_settings()


class TestMailIn(BaseModel):
    to: str = ""


@router.post("/api/admin/test-email")
async def test_email(body: TestMailIn, request: Request, u: User = Depends(admin_user)):
    try:
        to = users.clean_email(body.to) if body.to.strip() else u.email
    except UserError as e:
        raise HTTPException(400, str(e))
    try:
        # a real-looking notice (a one-line "if you read this, it works" is what spam filters distrust)
        await asyncio.to_thread(mailer.send, to, "Comprobación del correo", mailer.page("Comprobación del correo", [
            f"Hola, {esc(u.name.split()[0])}.",
            "Este es el correo de comprobación que has pedido desde Administración → Correo. Si te ha llegado, Mam-IA ya "
            "puede enviar los códigos para crear cuentas, las invitaciones, los recordatorios y los avisos de la "
            "suscripción.",
        ], ("Abrir Mam-IA", f"{base_url(request)}/app")))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"ok": True, "to": to}
