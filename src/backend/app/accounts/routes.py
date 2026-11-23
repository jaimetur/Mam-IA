"""Signing in and out, the account itself (name, look, password), forgotten passwords and deleting the account."""
from __future__ import annotations

import html

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.accounts import users, verify
from app.accounts.users import User, UserError
from app.billing.status import cancel_for, status
from app.core import db, mailer
from app.core.deps import (base_url, clear_session_cookie, client_ip, session_token, set_session_cookie,
                           signed_in_user)
from app.core.security import login_throttle, mail_throttle
from app.families import service as families
from app.notices import emails

router = APIRouter()


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/api/login")
def login(body: LoginIn, request: Request, response: Response):
    key = f"{client_ip(request)}|{body.email.strip().lower()}"
    if login_throttle.blocked(key):
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos y vuelve a probar.")
    with db.tx() as con:
        u = users.authenticate(con, body.email, body.password)
        if not u:
            login_throttle.fail(key)
            raise HTTPException(401, "El correo o la contraseña no son correctos.")
        token = users.create_session(con, u.id)
    login_throttle.reset(key)
    set_session_cookie(response, token)
    return {"ok": True, "user": u.public()}


@router.post("/api/logout")
def logout(request: Request, response: Response):
    with db.tx() as con:
        users.delete_session(con, session_token(request))
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/api/me")
def me(u: User = Depends(signed_in_user)):
    with db.ro() as con:
        fam = families.info(con, u.family_id)
    return {"user": u.public(), "family": fam, "billing": status(u.family_id)}


class MeIn(BaseModel):
    name: str | None = None
    email: str | None = None
    theme: str | None = None
    accent: str | None = None
    mailReminders: bool | None = None
    mailDigest: bool | None = None
    lang: str | None = None


@router.put("/api/me")
def update_me(body: MeIn, u: User = Depends(signed_in_user)):
    if body.email is not None and body.email.strip().lower() != u.email.lower():
        raise HTTPException(400, "Para cambiar el correo, confírmalo con el código que te enviamos (Cuenta → Correo).")
    try:
        with db.tx() as con:
            users.update_profile(con, u, body.name, body.theme, body.accent, mail_reminders=body.mailReminders,
                                 mail_digest=body.mailDigest, lang=body.lang)
            return {"user": users.get_user(con, u.id).public()}
    except UserError as e:
        raise HTTPException(400, str(e))


class EmailIn(BaseModel):
    email: str
    password: str


@router.post("/api/me/email")
def change_email(body: EmailIn, request: Request, u: User = Depends(signed_in_user)):
    """A new address for the account: a code goes to it, and it changes once the code is written (/api/web/verify)."""
    if mail_throttle.blocked(f"code|{u.id}"):
        raise HTTPException(429, "Ya te hemos enviado varios códigos. Espera un rato.")
    try:
        email = users.clean_email(body.email)
        with db.tx() as con:
            if not users.check_password(con, u.id, body.password):
                raise UserError("La contraseña no es correcta.")
            if email.lower() == u.email.lower():
                raise UserError("Ese ya es tu correo.")
            if users.get_by_email(con, email):
                raise UserError("Ya hay otra cuenta con ese correo.")
            pid, code = verify.start(con, "email", email, {"user": u.id, "name": u.name, "lang": u.lang})
            rec = verify.load(con, pid)
        mail_throttle.fail(f"code|{u.id}")
        verify.send(pid, rec, code)
    except UserError as e:
        raise HTTPException(400, str(e))
    return verify.public(pid, rec)


class PasswordIn(BaseModel):
    current: str = ""
    new: str


@router.post("/api/me/password")
def change_password(body: PasswordIn, request: Request, u: User = Depends(signed_in_user)):
    try:
        with db.tx() as con:
            if not u.must_change and not users.check_password(con, u.id, body.current):
                raise UserError("La contraseña actual no es correcta.")
            users.set_password(con, u.id, body.new, keep_session=session_token(request))
    except UserError as e:
        raise HTTPException(400, str(e))
    if not u.must_change:   # the first password of a new account is not news
        emails.password_changed(u)
    return {"ok": True}


class ForgotIn(BaseModel):
    email: str


@router.post("/api/password/forgot")
def forgot(body: ForgotIn, request: Request):
    """Email a link to choose a new password. Always answers the same, so nobody can find out who has an account."""
    email = body.email.strip().lower()
    if not mailer.configured():
        raise HTTPException(503, "Este servidor no puede enviar correos. Pide ayuda a quien administra tu familia.")
    if mail_throttle.blocked(email) or mail_throttle.blocked(client_ip(request)):
        raise HTTPException(429, "Ya te hemos enviado varios correos. Espera un rato y revisa tu bandeja de entrada.")
    mail_throttle.fail(email)
    mail_throttle.fail(client_ip(request))
    with db.tx() as con:
        u = users.get_by_email(con, email)
        token = users.create_reset(con, u.id) if u else None
    if u and token:
        link = f"{base_url(request)}/recuperar?t={token}"
        mailer.send_later(u.email, "Cambia tu contraseña", mailer.page(
            "Cambia tu contraseña",
            [f"Hola, {html.escape(u.name)}.", "Has pedido cambiar la contraseña de Mam-IA. El enlace vale durante 2 horas.",
             "Si no lo has pedido tú, no hagas nada: tu contraseña sigue igual."],
            ("Elegir una contraseña nueva", link)))
    return {"ok": True}


class ResetIn(BaseModel):
    token: str
    password: str


@router.post("/api/password/reset")
def reset(body: ResetIn, response: Response):
    try:
        with db.tx() as con:
            u = users.use_reset(con, body.token, body.password)
            token = users.create_session(con, u.id)
    except UserError as e:
        raise HTTPException(400, str(e))
    emails.password_changed(u)
    set_session_cookie(response, token)
    return {"ok": True}


class DeleteIn(BaseModel):
    password: str


@router.post("/api/me/delete")
def delete_me(body: DeleteIn, response: Response, u: User = Depends(signed_in_user)):
    """Delete one's own account (the family's owner alone in it deletes the whole family and its subscription)."""
    try:
        with db.tx() as con:
            if not users.check_password(con, u.id, body.password):
                raise UserError("La contraseña no es correcta.")
            f = families.get_family(con, u.family_id)
            alone = len(users.family_users(con, u.family_id)) == 1
            if f["owner_id"] == u.id and alone:
                cancel_for(con, u.family_id)
            families.leave(con, u)
    except UserError as e:
        raise HTTPException(400, str(e))
    emails.account_deleted(u.email, u.name, family_too=f["owner_id"] == u.id and alone)
    clear_session_cookie(response)
    return {"ok": True}
