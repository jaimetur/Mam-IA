"""Notifications in the browser (Web Push): the server's key, subscribing each device, and the loop that sends the
reminders of events and tasks when they are due, as notifications and by email. (The Android app sets its own alarms
through its native bridge.)"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.accounts.users import User
from app.core import config, crypto, db
from app.core.deps import signed_in_user
from app.data import store
from app.push import recur

log = logging.getLogger("mamia.push")
router = APIRouter()


def _keys() -> tuple[str, str]:
    """The server's VAPID keys (made once): the private key in PEM and the public one as the browsers want it."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    stored = db.get_setting("vapid")
    if stored and crypto.decrypt(stored.get("private")):
        return crypto.decrypt(stored["private"]), stored["public"]
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    raw = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    public = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    with db.tx() as con:
        db.set_setting(con, "vapid", {"private": crypto.encrypt(pem), "public": public})
    return pem, public


@router.get("/api/push/key")
def public_key():
    return {"key": _keys()[1]}


class SubIn(BaseModel):
    endpoint: str
    keys: dict


@router.post("/api/push/subscribe")
def subscribe(body: SubIn, u: User = Depends(signed_in_user)):
    if not body.endpoint.startswith("https://") or len(body.endpoint) > 1000 or not {"p256dh", "auth"} <= set(body.keys):
        raise HTTPException(400, "La suscripción no es válida.")
    with db.tx() as con:
        con.execute("INSERT INTO push_subs(endpoint, user_id, keys, created_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id, keys=excluded.keys",
                    (body.endpoint, u.id, json.dumps({k: body.keys[k] for k in ("p256dh", "auth")}), db.now_iso()))
    return {"ok": True}


class UnsubIn(BaseModel):
    endpoint: str


@router.post("/api/push/unsubscribe")
def unsubscribe(body: UnsubIn, u: User = Depends(signed_in_user)):
    with db.tx() as con:
        con.execute("DELETE FROM push_subs WHERE endpoint=? AND user_id=?", (body.endpoint, u.id))
    return {"ok": True}


def _send(sub: dict, payload: dict) -> bool:
    """Send one notification; False when the browser says the subscription is gone (it is then deleted)."""
    from py_vapid import Vapid01
    from pywebpush import WebPushException, webpush

    pem, _ = _keys()
    try:
        webpush({"endpoint": sub["endpoint"], "keys": json.loads(sub["keys"])}, json.dumps(payload, ensure_ascii=False),
                vapid_private_key=Vapid01.from_pem(pem.encode()), vapid_claims={"sub": f"mailto:{config.settings.contact_email}"},
                ttl=3600, timeout=15)
        return True
    except WebPushException as e:
        code = getattr(e.response, "status_code", None)
        if code in (404, 410):
            with db.tx() as con:
                con.execute("DELETE FROM push_subs WHERE endpoint=?", (sub["endpoint"],))
            return False
        log.warning("push failed (%s)", code)
        return True


@router.post("/api/push/test")
def test(u: User = Depends(signed_in_user)):
    with db.ro() as con:
        subs = [dict(r) for r in con.execute("SELECT * FROM push_subs WHERE user_id=?", (u.id,))]
    if not subs:
        raise HTTPException(400, "Este dispositivo todavía no tiene los avisos activados.")
    for s in subs:
        _send(s, {"title": "Mam-IA", "body": "Así te avisaremos de lo que toca.", "path": "/app", "tag": "prueba"})
    return {"ok": True, "devices": len(subs)}


def due_now(t0: datetime, t1: datetime) -> int:
    """Send the reminders due between t0 and t1 to the devices of the people concerned and, by email, to the accounts
    that want them. Returns how many notifications and emails were sent."""
    from app.accounts import users
    from app.core import mailer
    from app.notices import scheduler as notices

    mail_on = mailer.configured()
    with db.ro() as con:
        q = "SELECT DISTINCT u.family_id FROM push_subs p JOIN users u ON u.id=p.user_id"
        if mail_on:
            q += " UNION SELECT family_id FROM users WHERE mail_reminders=1"
        fams = [r[0] for r in con.execute(q)]
    sent = 0
    for fid in fams:
        with db.ro() as con:
            f = con.execute("SELECT tz FROM families WHERE id=?", (fid,)).fetchone()
            docs = {c: store.all_of(con, fid, c) for c in ("members", "events", "tasks")}
            subs = [dict(r) for r in con.execute(
                "SELECT p.*, u.member_id FROM push_subs p JOIN users u ON u.id=p.user_id WHERE u.family_id=?", (fid,))]
            accounts = users.family_users(con, fid) if mail_on else []
        if not f:
            continue
        for a in recur.alarms(docs, f["tz"], t0, t1):
            with db.tx() as con:
                fresh = con.execute("INSERT OR IGNORE INTO push_sent(family_id, key, sent_at) VALUES(?,?,?)",
                                    (fid, a["id"], db.now_iso())).rowcount
            if not fresh:
                continue
            targets = [s for s in subs if s["member_id"] in a["who"]] or subs   # nobody with an account: everyone
            for s in targets:
                _send(s, {"title": a["title"], "body": a["body"], "path": a["path"], "tag": a["id"], "id": a["id"]})
                sent += 1
            readers = notices.reminder_targets(accounts, a["who"])
            if readers:
                sent += notices.reminder(a, f["tz"], readers)
    return sent


async def loop() -> None:
    """Every minute, the reminders that became due since the last check (at most 10 minutes back), and the other
    automatic emails (the summary of the day, the notices of the subscription)."""
    last = datetime.now(timezone.utc) - timedelta(minutes=2)
    while True:
        await asyncio.sleep(60)
        now = datetime.now(timezone.utc)
        try:
            from app.notices import scheduler as notices
            await asyncio.to_thread(due_now, max(last, now - timedelta(minutes=10)), now)
            await asyncio.to_thread(notices.tick, now)
            with db.tx() as con:
                con.execute("DELETE FROM push_sent WHERE sent_at < ?", ((now - timedelta(days=30)).isoformat(timespec="seconds"),))
        except Exception:   # noqa: BLE001 — the loop must go on
            log.exception("push loop failed")
        last = now
