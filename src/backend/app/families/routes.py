"""The family: its name, the accounts in it, invitations, roles, handing it over, export, import and deleting it."""
from __future__ import annotations

import html
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.accounts import users, verify
from app.accounts.users import User, UserError
from app.billing.status import cancel_for
from app.core import crypto, db, i18n, mailer
from app.core.deps import (base_url, clear_session_cookie, client_ip, family_admin, json_body, set_session_cookie,
                           signed_in_user, writer)
from app.core.security import mail_throttle, password_problem
from app.families import service as families
from app.notices import emails

router = APIRouter()


def _fail(e: UserError):
    raise HTTPException(400, str(e))


@router.get("/api/family")
def get_family(u: User = Depends(signed_in_user)):
    with db.ro() as con:
        return families.info(con, u.family_id)


class FamilyIn(BaseModel):
    name: str


@router.put("/api/family")
def rename_family(body: FamilyIn, u: User = Depends(family_admin)):
    try:
        with db.tx() as con:
            families.rename(con, u.family_id, body.name)
            return families.info(con, u.family_id)
    except UserError as e:
        _fail(e)


class InviteIn(BaseModel):
    email: str = ""
    memberId: str | None = None


@router.post("/api/family/invites")
def invite(body: InviteIn, request: Request, u: User = Depends(family_admin)):
    """An invitation link to join the family: sent by email when there is an address, and returned so it can also be
    shared by WhatsApp or any other way."""
    if body.email.strip() and mail_throttle.blocked(f"invite|{u.id}"):
        raise HTTPException(429, "Has enviado muchas invitaciones seguidas. Espera un rato.")
    try:
        with db.tx() as con:
            code = families.create_invite(con, u, body.email, body.memberId)
            fam = families.get_family(con, u.family_id)
    except UserError as e:
        _fail(e)
    link = f"{base_url(request)}/unirse?c={code}"
    sent = False
    if body.email.strip():
        mail_throttle.fail(f"invite|{u.id}")
        sent = mailer.send_later(body.email.strip(), f"{u.name} te invita a {fam['name']}", mailer.page(
            f"{u.name} te invita a Mam-IA",
            [f"{html.escape(u.name)} quiere organizar con Mam-IA las cosas de <b>{html.escape(fam['name'])}</b>: la agenda, "
             "las tareas, la compra y lo que no se puede olvidar.",
             "Crea tu cuenta con este enlace (vale 14 días). Es gratis para ti: la familia ya tiene Mam-IA."],
            ("Unirme a la familia", link)))
    return {"link": link, "sent": sent}


@router.delete("/api/family/invites/{invite_id}")
def cancel_invite(invite_id: int, u: User = Depends(family_admin)):
    with db.tx() as con:
        families.cancel_invite(con, u.family_id, invite_id)
        return families.info(con, u.family_id)


@router.get("/api/invites/{code}")
def invite_preview(code: str):
    try:
        with db.ro() as con:
            return families.invite_preview(con, code)
    except UserError as e:
        raise HTTPException(404, str(e))


class AcceptIn(BaseModel):
    code: str
    name: str
    email: str
    password: str


@router.post("/api/invites/accept")
def accept(body: AcceptIn, request: Request, response: Response):
    """Join a family. When the invitation was sent to this same address, the link has proved it is a real one and the
    account is made at once; otherwise a code is emailed first (see /api/web/verify)."""
    if mail_throttle.blocked(f"accept|{client_ip(request)}"):
        raise HTTPException(429, "Demasiados intentos. Espera un rato.")
    try:
        with db.ro() as con:
            inv = families.invite_row(con, body.code)
        if inv["email"] and inv["email"].lower() == body.email.strip().lower():
            with db.tx() as con:
                u = families.accept_invite(con, body.code, body.name, body.email, body.password)
                con.execute("UPDATE users SET lang=? WHERE id=?", (i18n.request_lang(request), u.id))
                u = users.get_user(con, u.id)
                token = users.create_session(con, u.id)
            set_session_cookie(response, token)
            emails.member_joined(u)
            return {"ok": True}
        users.clean_name(body.name)
        email = users.clean_email(body.email)
        if inv["email"]:
            raise UserError(f"Esta invitación es para {inv['email']}: usa ese correo.")
        if p := password_problem(body.password):
            raise UserError(p)
        with db.ro() as con:
            if users.get_by_email(con, email):
                raise UserError("Ya hay una cuenta con ese correo: entra con ella.")
        with db.tx() as con:
            pid, code = verify.start(con, "join", email, {"invite": body.code, "name": " ".join(body.name.split()),
                                                          "pw": crypto.encrypt(body.password),
                                                          "lang": i18n.request_lang(request)})
            rec = verify.load(con, pid)
        mail_throttle.fail(f"accept|{client_ip(request)}")
        verify.send(pid, rec, code)
    except UserError as e:
        mail_throttle.fail(f"accept|{client_ip(request)}")
        _fail(e)
    return verify.public(pid, rec)


class RoleIn(BaseModel):
    role: str


@router.put("/api/family/accounts/{user_id}")
def set_role(user_id: int, body: RoleIn, u: User = Depends(family_admin)):
    try:
        with db.tx() as con:
            families.set_role(con, u, user_id, body.role)
            return families.info(con, u.family_id)
    except UserError as e:
        _fail(e)


@router.delete("/api/family/accounts/{user_id}")
def remove_account(user_id: int, u: User = Depends(family_admin)):
    if user_id == u.id:
        raise HTTPException(400, "Para irte de la familia, borra tu cuenta desde Cuenta.")
    try:
        with db.tx() as con:
            target = users.get_user(con, user_id)
            fam = families.get_family(con, u.family_id)
            families.remove_account(con, u, user_id)
            out = families.info(con, u.family_id)
    except UserError as e:
        _fail(e)
    emails.removed(target.email, target.name, u.name, fam["name"], lang=target.lang)
    return out


class TransferIn(BaseModel):
    userId: int


@router.post("/api/family/transfer")
def transfer(body: TransferIn, u: User = Depends(family_admin)):
    try:
        with db.tx() as con:
            families.transfer(con, u, body.userId)
            target = users.get_user(con, body.userId)
            fam = families.get_family(con, u.family_id)
            out = families.info(con, u.family_id)
    except UserError as e:
        _fail(e)
    emails.new_owner(target, u.name, fam["name"])
    return out


@router.get("/api/family/export")
def export(u: User = Depends(signed_in_user)):
    """A copy of all the family's data (JSON), to keep or to move to another server."""
    with db.ro() as con:
        data = families.export(con, u.family_id)
    body = json.dumps(data, ensure_ascii=False, indent=1)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="mamia-copia.json"'})


@router.post("/api/family/import")
async def import_copy(request: Request, u: User = Depends(writer)):
    if not u.family_admin:
        raise HTTPException(403, "Solo quien administra la familia puede importar una copia.")
    body = await json_body(request)
    docs = body.get("docs") if isinstance(body, dict) else None
    try:
        with db.tx() as con:
            return families.import_docs(con, u, docs)
    except UserError as e:
        _fail(e)


class DeleteFamilyIn(BaseModel):
    password: str


@router.post("/api/family/delete")
def delete_family(body: DeleteFamilyIn, response: Response, u: User = Depends(signed_in_user)):
    """Delete the whole family (only its owner): every account, all the data and the subscription."""
    try:
        with db.tx() as con:
            f = families.get_family(con, u.family_id)
            if f["owner_id"] != u.id:
                raise UserError("Solo quien paga la familia puede borrarla.")
            if not users.check_password(con, u.id, body.password):
                raise UserError("La contraseña no es correcta.")
            if u.is_admin and not con.execute("SELECT 1 FROM users WHERE is_admin=1 AND family_id<>?",
                                              (u.family_id,)).fetchone():
                raise UserError("En esta familia está la única cuenta de administración del servidor.")
            others = [x for x in users.family_users(con, u.family_id) if x.id != u.id]
            cancel_for(con, u.family_id)
            families.delete_family(con, u.family_id)
    except UserError as e:
        _fail(e)
    emails.account_deleted(u.email, u.name, family_too=True, lang=u.lang)
    if others:
        emails.family_deleted_by_owner([x.email for x in others], u.name, f["name"], langs={x.email: x.lang for x in others})
    clear_session_cookie(response)
    return {"ok": True}
