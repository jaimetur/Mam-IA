"""The family's subscription bought in the Android app (Google Play), and Administración → Google Play. As in
BodyLens, the app does the purchase with Google Play Billing and gives the page the purchase token; the server checks
it with Google (a service account of the Play Console) and acknowledges it.

Signing up in the app: the form and the email code go first, as on the website (/api/web/signup with store="play",
then /api/web/verify, which answers {play: true, pending}); then the app opens Google Play's purchase screen and the
page sends the token here (/api/play/complete): the family is made then."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.accounts import users
from app.accounts.users import User, UserError
from app.billing import play
from app.billing.status import save_play, status
from app.core import crypto, db, i18n
from app.core.deps import admin_user, set_session_cookie, signed_in_user
from app.families import service as families

router = APIRouter()


def _verified(token: str) -> dict:
    if not play.configured():
        raise HTTPException(503, "Las suscripciones de Google Play todavía no están disponibles.")
    try:
        info = play.check(token)
    except play.PlayError as e:
        raise HTTPException(400, str(e))
    if not info["active"]:
        raise HTTPException(400, "Esa suscripción no está activa.")
    return info


@router.get("/api/play/config")
def config():
    """Whether the Android app can offer the subscription, and the app's page in Google Play (for the landing)."""
    s = play.settings()
    return {"enabled": play.configured(), "package": s["package"], "product": s["product"],
            "storeUrl": (db.get_setting("play", {}) or {}).get("storeUrl", "")}


class CompleteIn(BaseModel):
    pending: str
    token: str


@router.post("/api/play/complete")
def complete(body: CompleteIn, response: Response):
    """The purchase of a sign-up whose email is already confirmed: makes the family and signs in."""
    from app.billing.web import _welcome
    token = body.token.strip()
    info = _verified(token)
    try:
        with db.tx() as con:
            r = con.execute("SELECT data FROM pending_signups WHERE id=?", (body.pending,)).fetchone()
            d = json.loads(r["data"]) if r else None
            if not d or d.get("kind") != "signup" or not d.get("verified") or d.get("store") != "play":
                raise UserError("Ese alta ya no está pendiente: vuelve a empezar.")
            if con.execute("SELECT 1 FROM play_subs WHERE token_hash=?", (play.token_hash(token),)).fetchone():
                raise UserError("Esa suscripción ya es de otra familia: entra con su cuenta.")
            u = families.create_family(con, d.get("family"), d["name"], d["email"], crypto.decrypt(d["pw"]))
            if i18n.clean(d.get("lang")):
                con.execute("UPDATE users SET lang=? WHERE id=?", (i18n.clean(d["lang"]), u.id))
            save_play(con, u.family_id, token, info)
            con.execute("DELETE FROM pending_signups WHERE id=?", (body.pending,))
            session = users.create_session(con, u.id)
            u = users.get_user(con, u.id)
    except UserError as e:
        raise HTTPException(400, str(e))
    if not info["acknowledged"]:
        play.acknowledge(token, info["product"])
    _welcome(u, "Google Play, plan anual" if info.get("basePlan") == "yearly" else "Google Play, plan mensual")
    set_session_cookie(response, session)
    return {"ok": True, "signedIn": True}


class LinkIn(BaseModel):
    token: str


def _owner(u: User) -> None:
    with db.ro() as con:
        f = families.get_family(con, u.family_id)
    if f["owner_id"] != u.id:
        raise HTTPException(403, "La suscripción la gestiona quien paga la familia.")


@router.post("/api/play/link")
def link(body: LinkIn, u: User = Depends(signed_in_user)):
    """A subscription bought in the app for the signed-in family: to renew one that is over, or to restore it."""
    _owner(u)
    token = body.token.strip()
    info = _verified(token)
    with db.tx() as con:
        other = con.execute("SELECT family_id FROM play_subs WHERE token_hash=?", (play.token_hash(token),)).fetchone()
        if other and other["family_id"] != u.family_id:
            raise HTTPException(400, "Esa suscripción es de otra familia.")
        save_play(con, u.family_id, token, info)
    if not info["acknowledged"]:
        play.acknowledge(token, info["product"])
    return status(u.family_id)


@router.post("/api/play/cancel")
def cancel(u: User = Depends(signed_in_user)):
    """Stops the renewals: the family keeps everything until the end of the paid period, then it is read-only."""
    _owner(u)
    with db.ro() as con:
        r = con.execute("SELECT * FROM play_subs WHERE family_id=?", (u.family_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Tu familia no tiene una suscripción de Google Play.")
    if not play.configured():
        raise HTTPException(503, "Las suscripciones de Google Play todavía no están disponibles.")
    try:
        play.cancel(crypto.decrypt(r["token_enc"]), r["product_id"])
        info = play.check(crypto.decrypt(r["token_enc"]))
    except Exception as e:   # noqa: BLE001 — Google did not answer
        raise HTTPException(502, str(e) or "Google Play no responde. Inténtalo más tarde.")
    with db.tx() as con:
        save_play(con, u.family_id, crypto.decrypt(r["token_enc"]), info)
    return status(u.family_id)


# ---------- Administración → Google Play ----------

class PlayIn(BaseModel):
    package: str = ""
    product: str = ""
    serviceAccount: str = ""        # the JSON key of the service account; empty = keep the stored one
    storeUrl: str | None = None     # the app's page in Google Play, once published (the landing page links it)
    remove: bool = False            # forget the service account


@router.get("/api/admin/play")
def get_play(u: User = Depends(admin_user)):
    s = play.settings()
    sa = s["sa"] or {}
    with db.ro() as con:
        n = con.execute("SELECT COUNT(*) FROM play_subs").fetchone()[0]
    return {"package": s["package"], "product": s["product"], "configured": play.configured(),
            "serviceAccount": sa.get("client_email", ""), "subscriptions": n,
            "storeUrl": (db.get_setting("play", {}) or {}).get("storeUrl", "")}


@router.put("/api/admin/play")
def put_play(body: PlayIn, u: User = Depends(admin_user)):
    stored = db.get_setting("play", {}) or {}
    new = {"package": body.package.strip() or stored.get("package") or play.DEFAULT_PACKAGE,
           "product": body.product.strip() or stored.get("product") or play.DEFAULT_PRODUCT,
           "storeUrl": stored.get("storeUrl", ""), "sa": stored.get("sa")}
    if body.storeUrl is not None:
        url = body.storeUrl.strip()
        if url and not url.startswith("https://play.google.com/"):
            raise HTTPException(400, "El enlace tiene que ser de Google Play (https://play.google.com/…).")
        new["storeUrl"] = url
    if body.remove:
        new["sa"] = None
    elif body.serviceAccount.strip():
        try:
            sa = json.loads(body.serviceAccount)
        except ValueError:
            raise HTTPException(400, "Pega el contenido del fichero JSON de la cuenta de servicio.")
        if not isinstance(sa, dict) or not sa.get("client_email") or "PRIVATE KEY" not in str(sa.get("private_key", "")):
            raise HTTPException(400, "Ese JSON no es la clave de una cuenta de servicio (faltan client_email o private_key).")
        new["sa"] = crypto.encrypt(sa)
    with db.tx() as con:
        db.set_setting(con, "play", new)
    return get_play(u)
