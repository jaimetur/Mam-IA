"""Whether a family can write: a free access (promotion code or given by an administrator), a website subscription
(Stripe) or one bought in the Android app (Google Play).

A family with neither (made on a server with OPEN_SIGNUP, or the administrator's own) never expires. When the free
access or the subscription is over, the family becomes read-only: everyone can still sign in, read, export their data
and renew; nothing is deleted."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from app.billing import codes, play, stripe
from app.core import crypto, db

REFRESH_MS = 2 * 86400 * 1000      # a period over for 2 days without news from the webhook: ask Stripe
PLAY_RECHECK_MS = 3600 * 1000       # a Google Play subscription past its end is asked to Google at most once an hour


def save_play(con, family_id: int, token: str, info: dict) -> None:
    """Keep the family's Google Play subscription (the token encrypted, and its hash to find it)."""
    import time as _t
    con.execute(
        "INSERT INTO play_subs(family_id, token_hash, token_enc, product_id, base_plan, state, expiry_ms, checked_at, "
        "created_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(family_id) DO UPDATE SET token_hash=excluded.token_hash, "
        "token_enc=excluded.token_enc, product_id=excluded.product_id, base_plan=excluded.base_plan, "
        "state=excluded.state, expiry_ms=excluded.expiry_ms, checked_at=excluded.checked_at",
        (family_id, play.token_hash(token), crypto.encrypt(token), info["product"], info.get("basePlan"), info["state"],
         info["expiry"], int(_t.time() * 1000), datetime.now(timezone.utc).isoformat(timespec="seconds")))
    if info.get("active"):
        con.execute("DELETE FROM lapses WHERE family_id=?", (family_id,))


def play_active(family_id: int, row) -> bool:
    """The Google Play subscription lets the family write (asking Google again, at most hourly, once it is past its
    end: it may have been renewed)."""
    now = int(time.time() * 1000)
    if row["expiry_ms"] > now:
        return True
    if now - row["checked_at"] < PLAY_RECHECK_MS or not play.configured():
        return False
    try:
        info = play.check(crypto.decrypt(row["token_enc"]))
    except Exception:   # noqa: BLE001 — Google unreachable: keep what is known
        return False
    with db.tx() as con:
        save_play(con, family_id, crypto.decrypt(row["token_enc"]), info)
    return bool(info["active"])


def _ms(sec) -> int:
    return int(sec or 0) * 1000


def method_of(sub: dict) -> str | None:
    """How the subscription is paid ("Visa ·4242", "Google Pay"…), when Stripe sent the payment method expanded."""
    pm = sub.get("default_payment_method")
    if not isinstance(pm, dict):
        return None
    card = pm.get("card") or {}
    wallet = (card.get("wallet") or {}).get("type")
    if wallet:
        return {"apple_pay": "Apple Pay", "google_pay": "Google Pay", "link": "Link"}.get(wallet, wallet.replace("_", " ").title())
    if card:
        return f"{(card.get('brand') or 'tarjeta').title()} ·{card.get('last4', '')}".strip()
    return (pm.get("type") or "").replace("_", " ").title() or None


def save_sub(con, family_id: int, sub: dict) -> None:
    item = ((sub.get("items") or {}).get("data") or [{}])[0]
    price = (item.get("price") or {}).get("id")
    plan = next((p for p, pid in stripe.settings()["prices"].items() if pid == price), None)
    end = sub.get("current_period_end") or item.get("current_period_end")
    con.execute(
        "INSERT INTO stripe_subs(family_id, customer_id, subscription_id, plan, status, period_end_ms, updated_at, method, "
        "cancel_end) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(family_id) DO UPDATE SET customer_id=excluded.customer_id, "
        "subscription_id=excluded.subscription_id, plan=excluded.plan, status=excluded.status, "
        "period_end_ms=excluded.period_end_ms, updated_at=excluded.updated_at, "
        "method=coalesce(excluded.method, stripe_subs.method), cancel_end=excluded.cancel_end",
        (family_id, sub.get("customer"), sub["id"], plan, sub.get("status", ""), _ms(end), stripe.now_iso(),
         method_of(sub), int(bool(sub.get("cancel_at_period_end")))))
    if sub.get("status") in stripe.ACTIVE:
        con.execute("DELETE FROM lapses WHERE family_id=?", (family_id,))


def sub_active(family_id: int, row) -> bool:
    """The website subscription lets the family write (asking Stripe if the webhook has been silent too long)."""
    if row["status"] in stripe.ACTIVE and row["period_end_ms"] + REFRESH_MS < time.time() * 1000 and stripe.configured():
        try:
            sub = stripe.call("GET", f"/subscriptions/{row['subscription_id']}")
            with db.tx() as con:
                save_sub(con, family_id, sub)
            return sub.get("status") in stripe.ACTIVE
        except stripe.StripeError:
            pass
    return row["status"] in stripe.ACTIVE


def _rows(family_id: int):
    with db.ro() as con:
        g = con.execute("SELECT * FROM grants WHERE family_id=?", (family_id,)).fetchone()
        w = con.execute("SELECT * FROM stripe_subs WHERE family_id=?", (family_id,)).fetchone()
        p = con.execute("SELECT * FROM play_subs WHERE family_id=?", (family_id,)).fetchone()
    return g, w, p


def expired(family_id: int) -> bool:
    g, w, p = _rows(family_id)
    if g is not None and codes.active(g):
        return False
    if w is not None and sub_active(family_id, w):
        return False
    if p is not None and play_active(family_id, p):
        return False
    return g is not None or w is not None or p is not None


def mark_lapse(family_id: int) -> str | None:
    """When the family became read-only (recorded the first time it is seen), or None while it can write."""
    if not expired(family_id):
        return None
    with db.tx() as con:
        r = con.execute("SELECT lapsed_at FROM lapses WHERE family_id=?", (family_id,)).fetchone()
        if r:
            return r["lapsed_at"]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute("INSERT INTO lapses(family_id, lapsed_at) VALUES(?,?)", (family_id, now))
        return now


def status(family_id: int) -> dict:
    """What the family has, for the account page and the app's banner."""
    g, w, p = _rows(family_id)
    lapsed = mark_lapse(family_id)
    extra = {"readOnly": True, "lapsedAt": lapsed} if lapsed else {"readOnly": False}
    if w is not None:
        return {"plan": "web", "active": sub_active(family_id, w), "expiry": w["period_end_ms"], "basePlan": w["plan"],
                "state": w["status"], "cancelAtEnd": bool(w["cancel_end"]), "method": w["method"],
                **({"giftUntil": g["until_ms"]} if g is not None and codes.active(g) else {}), **extra}
    if p is not None and (g is None or not codes.active(g)):
        return {"plan": "play", "active": play_active(family_id, p), "expiry": p["expiry_ms"], "basePlan": p["base_plan"],
                "state": p["state"], "cancelAtEnd": p["state"] == "SUBSCRIPTION_STATE_CANCELED",
                "package": play.settings()["package"], **extra}
    if g is not None:
        return {"plan": "gift", "active": codes.active(g), "expiry": g["until_ms"], "code": g["code"], **extra}
    return {"plan": "free", "active": True, **extra}


def summary(con, family_id: int) -> dict:
    """The kind of access, without asking Stripe (for the list in Administración)."""
    g = con.execute("SELECT until_ms, code FROM grants WHERE family_id=?", (family_id,)).fetchone()
    w = con.execute("SELECT status, period_end_ms, plan, method FROM stripe_subs WHERE family_id=?", (family_id,)).fetchone()
    out: dict = {"kind": "free"}
    pl = con.execute("SELECT state, expiry_ms, base_plan FROM play_subs WHERE family_id=?", (family_id,)).fetchone()
    if pl is not None:
        out = {"kind": "play", "state": pl["state"], "expiry": pl["expiry_ms"], "plan": pl["base_plan"]}
    if w is not None:
        out = {"kind": "web", "state": w["status"], "expiry": w["period_end_ms"], "plan": w["plan"], "method": w["method"]}
    if g is not None:
        gift = {"giftUntil": g["until_ms"], "code": g["code"]}
        out = {**out, "gift": True, **gift} if out["kind"] != "free" else {"kind": "gift", **gift}
    return out


def cancel_for(con, family_id: int) -> None:
    """Cancel the family's Stripe subscription at once (it is being deleted). Best effort."""
    w = con.execute("SELECT subscription_id FROM stripe_subs WHERE family_id=?", (family_id,)).fetchone()
    if w is not None:
        try:
            stripe.call("DELETE", f"/subscriptions/{w['subscription_id']}")
        except Exception:   # noqa: BLE001 — never stop a deletion
            pass
    pl = con.execute("SELECT token_enc, product_id FROM play_subs WHERE family_id=?", (family_id,)).fetchone()
    if pl is not None and play.configured():
        try:   # stops the renewals in Google Play
            play.cancel(crypto.decrypt(pl["token_enc"]), pl["product_id"])
        except Exception:   # noqa: BLE001 — never stop a deletion
            pass
