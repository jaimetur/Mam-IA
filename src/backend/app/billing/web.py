"""Sign-up and the family's subscription on the website (Stripe): plans, signing up (with a promotion code, paying, or
free on an open server), coming back from the payment, renewing, changing plan, cancelling, Stripe's webhook, and the
promotions and Stripe settings of Administración. Adapted from BodyLens; here the subscription is the family's."""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.accounts import users
from app.accounts.users import User, UserError
from app.billing import codes, play, stripe
from app.billing.status import save_sub, status
from app.core import config, crypto, db, i18n
from app.accounts import verify
from app.core.deps import admin_user, base_url, client_ip, family_admin, set_session_cookie, signed_in_user
from app.core.security import mail_throttle, password_problem
from app.families import service as families
from app.notices import emails

router = APIRouter()


@router.get("/api/web/plans")
def plans():
    """The subscription plans (the landing page and the sign-up use them)."""
    return {"enabled": stripe.configured(), "openSignup": config.settings.open_signup, "trialDays": stripe.TRIAL_DAYS,
            "plans": [{"plan": p, "cents": c, "currency": "EUR", "interval": i} for p, (i, c, _) in stripe.PLANS.items()]}


@router.get("/api/promos")
def get_promos():
    """The promotions shown on the landing page (public codes and the places they have left)."""
    return {"promos": codes.promos()}


class SignupIn(BaseModel):
    plan: str = "yearly"
    name: str
    email: str
    password: str
    family: str = ""
    code: str = ""   # a promotion or invitation code: the family is free for its time and made at once
    store: str = ""  # "play": paid in the Android app with Google Play (app.billing.play_routes), else Stripe


def _check(body: SignupIn) -> None:
    users.clean_name(body.name)
    users.clean_email(body.email)
    families.clean_family_name(body.family)
    if p := password_problem(body.password):
        raise UserError(p)
    with db.ro() as con:
        if users.get_by_email(con, body.email):
            raise UserError("Ya hay una cuenta con ese correo: entra con ella.")
    if body.code.strip() and not codes.valid(body.code):
        raise UserError("Ese código no es válido o ya no quedan plazas.")


def _free(code: str) -> bool:
    """Made at once, without paying: with a promotion code, or on an open server without Stripe."""
    return bool(code.strip()) or (config.settings.open_signup and not stripe.configured())


@router.post("/api/web/signup")
def signup(body: SignupIn, request: Request):
    """Check the details and email a code to confirm the address: the family is made (or the payment starts) once
    the code is written in /api/web/verify. An email is required, and it has to be a real one."""
    if mail_throttle.blocked(f"code|{client_ip(request)}") or mail_throttle.blocked(f"code|{body.email.strip().lower()}"):
        raise HTTPException(429, "Ya te hemos enviado varios códigos. Espera un rato y revisa tu bandeja de entrada.")
    try:
        _check(body)
        if not _free(body.code):
            if body.store == "play":
                if not play.configured():
                    raise HTTPException(503, "Las suscripciones de Google Play todavía no están disponibles.")
            elif not stripe.configured():
                raise HTTPException(503, "Las altas con pago todavía no están disponibles. Si tienes un código, escríbelo.")
            if body.plan not in stripe.PLANS:
                raise UserError("Ese plan no existe.")
        data = {"name": " ".join(body.name.split()), "pw": crypto.encrypt(body.password), "family": body.family,
                "plan": body.plan, "code": body.code.strip(), "lang": i18n.request_lang(request),
                "store": "play" if body.store == "play" else ""}
        with db.tx() as con:
            pid, code = verify.start(con, "signup", body.email.strip(), data)
            rec = verify.load(con, pid)
        mail_throttle.fail(f"code|{client_ip(request)}")
        mail_throttle.fail(f"code|{body.email.strip().lower()}")
        verify.send(pid, rec, code)
    except UserError as e:
        raise HTTPException(400, str(e))
    return verify.public(pid, rec)


def _make_family(con, d: dict) -> User:
    """The family of a confirmed sign-up (with the free access of its code, if it has one)."""
    u = families.create_family(con, d.get("family"), d["name"], d["email"], crypto.decrypt(d["pw"]))
    if d.get("code"):
        c = codes.use(con, d["code"])
        if c is None:
            raise UserError("Ese código ya no es válido o ya no quedan plazas. Vuelve a empezar sin código o con otro.")
        codes.grant(con, u.family_id, codes.norm(c["code"]), codes.until_ms(c["duration"]))
    return u


def _welcome(u: User, how: str) -> None:
    """The emails of a new family: welcome to its owner, and a notice to the server's administrators."""
    with db.ro() as con:
        fam = families.get_family(con, u.family_id)
        admins = [users.User.from_row(r) for r in con.execute("SELECT * FROM users WHERE is_admin=1")]
    emails.welcome_owner(u, fam["name"])
    emails.new_family_to_admins(admins, u, fam["name"], how)


class VerifyIn(BaseModel):
    id: str
    code: str = ""


@router.post("/api/web/verify")
def verify_code(body: VerifyIn, request: Request, response: Response):
    """The code of the email: makes the family (or opens the payment), the account of someone joining a family, or the
    new address of an account."""
    try:
        d = verify.check(body.id, body.code)
        kind = d["kind"]
        if kind == "signup" and not _free(d.get("code", "")) and d.get("store") == "play":
            return {"play": True, "pending": body.id, "plan": d.get("plan") or "yearly"}   # now the purchase in the app
        if kind == "signup" and not _free(d.get("code", "")):
            if not stripe.configured():
                raise HTTPException(503, "Las altas con pago todavía no están disponibles. Si tienes un código, escríbelo.")
            try:   # the pending sign-up waits for the payment (see _family_for)
                return {"url": stripe.checkout(d.get("plan") or "yearly", body.id, d["email"], base_url(request))}
            except stripe.StripeError as e:
                raise HTTPException(502, str(e))
        with db.tx() as con:
            if kind == "signup":
                u = _make_family(con, d)
            elif kind == "join":
                u = families.accept_invite(con, d["invite"], d["name"], d["email"], crypto.decrypt(d["pw"]))
            elif kind == "email":
                old = users.get_user(con, d["user"])
                if old is None:
                    raise UserError("Esa cuenta ya no existe.")
                users.update_profile(con, old, email=d["email"])
                u = users.get_user(con, old.id)
            else:
                raise UserError("Esa confirmación no es válida: vuelve a empezar.")
            if kind != "email" and d.get("lang"):   # the language the person was using
                con.execute("UPDATE users SET lang=? WHERE id=?", (i18n.clean(d["lang"]), u.id))
                u = users.get_user(con, u.id)
            verify.forget(con, body.id)
            token = users.create_session(con, u.id) if kind != "email" else None
    except UserError as e:
        raise HTTPException(400, str(e))
    if kind == "signup":
        _welcome(u, f"código {d['code'].upper()}" if d.get("code") else "alta libre (servidor sin pagos)")
    elif kind == "join":
        emails.member_joined(u)
    else:
        emails.email_changed(old.email, u)
        return {"ok": True, "user": u.public()}
    set_session_cookie(response, token)
    return {"ok": True, "signedIn": True}


class ResendIn(BaseModel):
    id: str


@router.post("/api/web/verify/resend")
def resend_code(body: ResendIn):
    try:
        with db.tx() as con:
            rec, code = verify.resend(con, body.id)
        verify.send(body.id, rec, code)
    except UserError as e:
        raise HTTPException(400, str(e))
    return verify.public(body.id, rec)


def _family_for(session: dict) -> User | None:
    """Make the family of a completed checkout (once), or link the renewal of an existing one. The account returned is
    the family's owner."""
    sub = session.get("subscription")
    if isinstance(sub, str) or (sub and not isinstance(sub.get("default_payment_method"), dict) and sub.get("default_payment_method")):
        sub = stripe.call("GET", f"/subscriptions/{sub if isinstance(sub, str) else sub['id']}", {"expand": ["default_payment_method"]})
    if not sub or session.get("status") != "complete":
        return None
    meta = session.get("metadata") or {}
    with db.tx() as con:
        if meta.get("family"):                                 # renewal of an existing family
            f = families.get_family(con, int(meta["family"]))
            if f:
                save_sub(con, f["id"], sub)
                return users.get_user(con, f["owner_id"]) if f["owner_id"] else None
            return None
        done = con.execute("SELECT family_id FROM stripe_subs WHERE subscription_id=?", (sub["id"],)).fetchone()
        if done:
            f = families.get_family(con, done["family_id"])
            return users.get_user(con, f["owner_id"]) if f and f["owner_id"] else None
        row = con.execute("SELECT data FROM pending_signups WHERE id=?", (meta.get("pending", ""),)).fetchone()
        if not row:
            return None
        d = json.loads(row["data"])
        if "check" in d and not d.get("verified"):   # the email was never confirmed
            return None
        u = families.create_family(con, d.get("family"), d["name"], d["email"], crypto.decrypt(d["pw"]))
        if i18n.clean(d.get("lang")):
            con.execute("UPDATE users SET lang=? WHERE id=?", (i18n.clean(d["lang"]), u.id))
            u = users.get_user(con, u.id)
        save_sub(con, u.family_id, sub)
        con.execute("DELETE FROM pending_signups WHERE id=?", (meta.get("pending", ""),))
        made = u
    _welcome(made, "de pago, plan anual" if d.get("plan") == "yearly" else "de pago, plan mensual")
    return made


class CompleteIn(BaseModel):
    session_id: str


@router.post("/api/web/complete")
def complete(body: CompleteIn, response: Response):
    """Back from Stripe's checkout: the family (made now, or by the webhook a moment before) and a session."""
    try:
        session = stripe.call("GET", f"/checkout/sessions/{body.session_id}",
                              {"expand": ["subscription", "subscription.default_payment_method"]})
    except stripe.StripeError as e:
        raise HTTPException(400, str(e))
    try:
        u = _family_for(session)
    except UserError as e:
        raise HTTPException(400, str(e))
    if not u:
        raise HTTPException(400, "El pago todavía no está confirmado. Espera un momento y vuelve a intentarlo.")
    fresh = (session.get("created") or 0) > time.time() - 3600      # sign in only right after paying
    if fresh:
        with db.tx() as con:
            set_session_cookie(response, users.create_session(con, u.id))
    return {"ok": True, "signedIn": fresh, "email": u.email}


class PlanIn(BaseModel):
    plan: str


def _owner(u: User) -> None:
    with db.ro() as con:
        f = families.get_family(con, u.family_id)
    if f["owner_id"] != u.id:
        raise HTTPException(403, "La suscripción la gestiona quien paga la familia.")


@router.post("/api/web/renew")
def renew(body: PlanIn, request: Request, u: User = Depends(signed_in_user)):
    """A new subscription for a family whose free time or subscription is over (no free trial again)."""
    _owner(u)
    if not stripe.configured():
        raise HTTPException(503, "Los pagos con tarjeta todavía no están disponibles en este servidor.")
    price = stripe.settings()["prices"].get(body.plan)
    if not price:
        raise HTTPException(400, "Ese plan no existe.")
    with db.ro() as con:
        w = con.execute("SELECT customer_id FROM stripe_subs WHERE family_id=?", (u.family_id,)).fetchone()
    params = {"mode": "subscription", "line_items": [{"price": price, "quantity": 1}],
              "metadata": {"family": str(u.family_id)}, "locale": "es",
              "success_url": f"{base_url(request)}/bienvenida?session_id={{CHECKOUT_SESSION_ID}}",
              "cancel_url": f"{base_url(request)}/cuenta"}
    if w:
        params["customer"] = w["customer_id"]
    else:
        params["customer_email"] = u.email
    try:
        return {"url": stripe.call("POST", "/checkout/sessions", params)["url"]}
    except stripe.StripeError as e:
        raise HTTPException(502, str(e))


def _my_sub(u: User):
    _owner(u)
    with db.ro() as con:
        w = con.execute("SELECT * FROM stripe_subs WHERE family_id=?", (u.family_id,)).fetchone()
    if not w:
        raise HTTPException(404, "Tu familia no tiene una suscripción de pago.")
    if not stripe.configured():
        raise HTTPException(503, "Los pagos con tarjeta todavía no están disponibles en este servidor.")
    return w


def _update(u: User, w, params: dict) -> dict:
    try:
        sub = stripe.call("POST", f"/subscriptions/{w['subscription_id']}", params)
    except stripe.StripeError as e:
        raise HTTPException(502, str(e))
    with db.tx() as con:
        save_sub(con, u.family_id, sub)
    return status(u.family_id)


@router.post("/api/web/change")
def change_plan(body: PlanIn, u: User = Depends(signed_in_user)):
    """Monthly ↔ yearly: the new price applies from the next renewal (nothing is charged or refunded now)."""
    w = _my_sub(u)
    price = stripe.settings()["prices"].get(body.plan)
    if not price:
        raise HTTPException(400, "Ese plan no existe.")
    if w["plan"] == body.plan:
        raise HTTPException(400, "Ya tienes ese plan.")
    try:
        cur = stripe.call("GET", f"/subscriptions/{w['subscription_id']}")
    except stripe.StripeError as e:
        raise HTTPException(502, str(e))
    if cur.get("status") not in stripe.ACTIVE:
        raise HTTPException(400, "Tu suscripción ha terminado: renuévala con el plan que quieras.")
    item = ((cur.get("items") or {}).get("data") or [{}])[0]
    return _update(u, w, {"items": [{"id": item.get("id"), "price": price}], "proration_behavior": "none",
                          "cancel_at_period_end": "false"})


@router.post("/api/web/cancel")
def cancel(u: User = Depends(signed_in_user)):
    """Cancel without deleting anything: the family keeps everything until the end of the paid period, then it is
    read-only until it is renewed."""
    return _update(u, _my_sub(u), {"cancel_at_period_end": "true"})


@router.post("/api/web/resume")
def resume(u: User = Depends(signed_in_user)):
    return _update(u, _my_sub(u), {"cancel_at_period_end": "false"})


@router.post("/api/web/portal")
def manage(request: Request, u: User = Depends(signed_in_user)):
    """Stripe's page to change the card or see the invoices."""
    w = _my_sub(u)
    try:
        return {"url": stripe.portal(w["customer_id"], base_url(request))}
    except stripe.StripeError as e:
        raise HTTPException(502, str(e))


@router.post("/api/web/webhook")
async def webhook(request: Request):
    """Stripe tells what happens to each subscription (made, renewed, payment failed, cancelled)."""
    payload = await request.body()
    try:
        ev = stripe.verify_webhook(payload, request.headers.get("stripe-signature", ""))
    except stripe.StripeError as e:
        raise HTTPException(400, str(e))
    obj = (ev.get("data") or {}).get("object") or {}
    kind = ev.get("type", "")
    try:
        if kind == "checkout.session.completed":
            _family_for(obj)
        elif kind.startswith("customer.subscription."):
            with db.tx() as con:
                r = con.execute("SELECT family_id FROM stripe_subs WHERE subscription_id=?", (obj.get("id"),)).fetchone()
                if r:
                    save_sub(con, r["family_id"], obj)
    except (UserError, stripe.StripeError):
        pass   # answered 200 anyway: Stripe would retry a failure forever
    return {"ok": True}


@router.get("/api/billing")
def my_billing(u: User = Depends(signed_in_user)):
    with db.ro() as con:
        f = families.get_family(con, u.family_id)
    return {**status(u.family_id), "owner": f["owner_id"] == u.id, "stripe": stripe.configured()}


class RedeemIn(BaseModel):
    code: str


@router.post("/api/billing/code")
def redeem(body: RedeemIn, u: User = Depends(family_admin)):
    """Use a promotion code in an existing family (e.g. to extend a free period)."""
    try:
        with db.tx() as con:
            c = codes.use(con, body.code)
            if c is None:
                raise UserError("Ese código no es válido o ya no quedan plazas.")
            codes.grant(con, u.family_id, codes.norm(c["code"]), codes.until_ms(c["duration"]))
    except UserError as e:
        raise HTTPException(400, str(e))
    return status(u.family_id)


# ---------- Administración ----------

class StripeIn(BaseModel):
    secret: str = ""     # empty = keep the stored one
    webhook: str = ""
    remove: bool = False


@router.get("/api/admin/stripe")
def get_stripe(request: Request, u: User = Depends(admin_user)):
    s = stripe.settings()
    with db.ro() as con:
        n = con.execute("SELECT COUNT(*) FROM stripe_subs").fetchone()[0]
    return {"configured": stripe.configured(), "webhookSet": bool(s["webhook"]), "prices": s["prices"],
            "live": bool(s["secret"] and s["secret"].startswith("sk_live")), "subscriptions": n,
            "webhookUrl": f"{base_url(request)}/api/web/webhook"}


@router.put("/api/admin/stripe")
def put_stripe(body: StripeIn, request: Request, u: User = Depends(admin_user)):
    stored = db.get_setting("stripe", {}) or {}
    new = dict(stored)
    if body.remove:
        new = {}
    else:
        if body.secret.strip():
            if not body.secret.strip().startswith(("sk_", "rk_")):
                raise HTTPException(400, "Pega la clave secreta de Stripe (empieza por sk_).")
            try:
                new["prices"] = stripe.ensure_prices(body.secret.strip())
            except stripe.StripeError as e:
                raise HTTPException(400, str(e))
            new["secret"] = crypto.encrypt(body.secret.strip())
        if body.webhook.strip():
            if not body.webhook.strip().startswith("whsec_"):
                raise HTTPException(400, "Pega el secreto de firma del webhook (empieza por whsec_).")
            new["webhook"] = crypto.encrypt(body.webhook.strip())
    with db.tx() as con:
        db.set_setting(con, "stripe", new)
    return get_stripe(request, u)


class CodeIn(BaseModel):
    code: str
    duration: str = "1y"     # 1m, 3m, 6m, 1y, life or a date YYYY-MM-DD (free until that day)
    expires: str = ""        # YYYY-MM-DD: the last day it can be used ("" = no end)
    max: int | None = None   # how many families can use it (None = no limit)
    public: bool = False     # shown on the landing page as a promotion
    aliases: list[str] = []


class CodesIn(BaseModel):
    codes: list[CodeIn]


@router.get("/api/admin/codes")
def get_codes(u: User = Depends(admin_user)):
    return {"codes": codes.codes()}


@router.put("/api/admin/codes")
def put_codes(body: CodesIn, u: User = Depends(admin_user)):
    clean: list[dict] = []
    old = {codes.norm(c["code"]): c for c in codes.codes()}
    taken: set[str] = set()
    for c in body.codes:
        code = c.code.strip()
        if not code:
            continue
        if len(code) > 60:
            raise HTTPException(400, "Un código no puede tener más de 60 caracteres.")
        al = [a.strip() for a in c.aliases if a.strip() and len(a.strip()) <= 60]
        names = {codes.norm(code), *(codes.norm(a) for a in al)}
        if names & taken:
            raise HTTPException(400, "Hay dos códigos (o alias) iguales.")
        taken |= names
        d = codes.clean_duration(c.duration)
        if not d:
            raise HTTPException(400, "La duración de un código no es válida.")
        e = codes.clean_expiry(c.expires)
        if e is None:
            raise HTTPException(400, "Esa fecha de caducidad no es válida.")
        if c.max is not None and not 1 <= c.max <= 1_000_000:
            raise HTTPException(400, "El número máximo de familias de un código tiene que ser de 1 a 1 000 000.")
        used = (old.get(codes.norm(code)) or {}).get("used", 0)
        if c.max is not None and used >= c.max:
            raise HTTPException(400, f"El código {code} ya se ha usado {used} veces: pon un máximo mayor.")
        clean.append({"code": code, "aliases": [a for a in al if codes.norm(a) != codes.norm(code)], "duration": d,
                      "expires": e, "max": c.max, "used": used, "public": c.public})
    with db.tx() as con:
        db.set_setting(con, "codes", clean)
    return {"codes": codes.codes()}
