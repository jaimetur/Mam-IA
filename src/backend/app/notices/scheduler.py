"""The emails that go by themselves: the reminders of events and tasks (with the push notifications, see
app.push.routes.due_now), the summary of the day every morning and the notices of the subscription (free access about
to end, read-only, a payment that failed). Every one is sent once: mail_sent and push_sent remember them."""
from __future__ import annotations

import logging
import math
import time
from datetime import date, datetime, timedelta, timezone
from html import escape as esc
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.accounts import users
from app.billing import codes, status
from app.billing import stripe as stripe_api
from app.core import db, mailer
from app.data import store
from app.notices import emails
from app.push import recur

log = logging.getLogger("mamia.notices")
DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
DIGEST_FROM, DIGEST_UNTIL = 7, 12          # the summary of the day goes from 07:00 (local), never after noon
ENDING_DAYS = (7, 1)                       # notices before a free access ends
BILLING_EVERY = 6 * 3600


def long_day(d: date) -> str:
    return f"{DAYS[d.weekday()]} {d.day} de {MONTHS[d.month - 1]}"


def _once(key: str) -> bool:
    """True the first time a key is seen (the email is then sent); False afterwards."""
    with db.tx() as con:
        return con.execute("INSERT OR IGNORE INTO mail_sent(key, sent_at) VALUES(?,?)", (key, db.now_iso())).rowcount == 1


# ---------- reminders ----------

def reminder(a: dict, tz_name: str, accounts: list) -> int:
    """Email one reminder (from recur.alarms) to each account, each with its own link to stop them."""
    tz = ZoneInfo(tz_name or "Europe/Madrid")
    kind, _, rest = a["id"].partition(":")
    the_day = date.fromisoformat(rest.rsplit(":", 1)[1])
    today = a["at"].astimezone(tz).date()
    when = "Hoy" if the_day == today else "Mañana" if the_day == today + timedelta(days=1) else long_day(the_day).capitalize()
    if kind == "tk":
        link = ("Marcar como hecha", f"{emails.base()}/app?hecho={quote(a['id'], safe='')}#tareas")
    else:
        link = ("Ver la agenda", f"{emails.base()}/app#agenda")
    sent = 0
    for u in accounts:
        off = emails.unsubscribe_link(u.id, "recordatorios")
        mailer.send_later(u.email, f"{a['title']} · {when.lower() if when in ('Hoy', 'Mañana') else when}", mailer.page(
            a["title"], [f"<b>{esc(when)}</b> · {esc(a['body'])}"], link,
            foot=emails.unsubscribe_foot(off, "los recordatorios por correo")), unsubscribe=off)
        sent += 1
    return sent


def reminder_targets(accounts: list, who: list[str]) -> list:
    """The accounts of the people concerned (when none of them has an account, everybody's) that want reminders by
    email."""
    concerned = [u for u in accounts if u.member_id in who] or accounts
    return [u for u in concerned if u.mail_reminders]


# ---------- the summary of the day ----------

def _events_on(docs: dict, d: date, name) -> list[tuple[str, str]]:
    out = []
    for e in docs.get("events", {}).values():
        if not e.get("start"):
            continue
        if not recur.occurs_on(date.fromisoformat(e["start"][:10]), e.get("repeat"), d) or d.isoformat() in (e.get("exdates") or []):
            continue
        hhmm = "" if e.get("allDay") or len(e["start"]) == 10 else e["start"][11:16]
        who = [name(w) for w in (e.get("who") or []) if name(w)]
        bits = [esc(e["title"]) + (f" · {esc(', '.join(who))}" if who else "")]
        if e.get("driver") and name(e["driver"]):
            bits.append(f"lleva {esc(name(e['driver']))}")
        if e.get("pickup") and name(e["pickup"]):
            bits.append(f"recoge {esc(name(e['pickup']))}")
        if e.get("place"):
            bits.append(esc(e["place"]))
        out.append((hhmm or "00:00", f"<b>{hhmm or 'Todo el día'}</b> · " + " · ".join(bits)))
    return sorted(out)


def digest_html(docs: dict, d: date, me_member: str | None) -> tuple[str, list[str]] | None:
    """Subject and paragraphs of the summary of day `d`, or None when there is nothing to tell."""
    members = docs.get("members", {})
    name = lambda mid: (members.get(mid) or {}).get("name", "")   # noqa: E731
    events = [h for _, h in _events_on(docs, d, name)]
    tasks, late = [], []
    for t in docs.get("tasks", {}).values():
        if t.get("done") or not t.get("due"):
            continue
        mine = " <b>(te toca)</b>" if me_member and t.get("who") == me_member else (
            f" · {esc(name(t['who']))}" if t.get("who") and name(t["who"]) else "")
        line = (f"<b>{t['time']}</b> · " if t.get("time") else "") + esc(t["title"]) + mine
        if t["due"] == d.isoformat():
            tasks.append((t.get("time") or "99", line))
        elif t["due"] < d.isoformat():
            late.append((t["due"], line))
    meals = {m.get("slot"): m for m in docs.get("meals", {}).values() if m.get("date") == d.isoformat()}
    shop_lists = {lid for lid, li in docs.get("lists", {}).items() if li.get("kind", "compra") == "compra"}
    to_buy = sum(1 for it in docs.get("items", {}).values() if it.get("list") in shop_lists and not it.get("done"))
    if not (events or tasks or late):
        return None
    ul = lambda rows: "<br>".join(rows)   # noqa: E731
    paras = []
    paras.append("<b>Planes</b><br>" + (ul(events) if events else "Ningún plan apuntado para hoy."))
    if tasks:
        paras.append("<b>Tareas de hoy</b><br>" + ul([x for _, x in sorted(tasks)]))
    if late:
        rows = [x for _, x in sorted(late)]
        paras.append("<b>Pendientes de días anteriores</b><br>" + ul(rows[:8]) + (f"<br>…y {len(rows) - 8} más" if len(rows) > 8 else ""))
    food = [(f"Comida: {esc(m.get('dish') or m.get('school') or '')}" if s == "comida" else f"Cena: {esc(m.get('dish') or m.get('school') or '')}")
            for s, m in sorted(meals.items(), key=lambda x: x[0] != "comida") if m.get("dish") or m.get("school")]
    if food:
        paras.append("<b>Menú</b><br>" + "<br>".join(food))
    if to_buy:
        paras.append("En la lista de la compra hay 1 cosa por comprar." if to_buy == 1   # whole sentences: translatable
                     else f"En la lista de la compra hay {to_buy} cosas por comprar.")
    n_ev, n_tk = len(events), len(tasks)
    parts = [("1 plan" if n_ev == 1 else f"{n_ev} planes") if n_ev else "",   # whole phrases: translatable
             ("1 tarea" if n_tk == 1 else f"{n_tk} tareas") if n_tk else ""]
    subject = "Tu día: " + (" y ".join(p for p in parts if p) or f"{len(late)} pendientes")
    return subject, paras


def digests(now: datetime) -> int:
    """The summary of the day for the accounts that want it, once a day, from 07:00 in the family's time zone."""
    if not mailer.configured():
        return 0
    with db.ro() as con:
        fams = [r[0] for r in con.execute("SELECT DISTINCT family_id FROM users WHERE mail_digest=1")]
    sent = 0
    for fid in fams:
        with db.ro() as con:
            f = con.execute("SELECT tz FROM families WHERE id=?", (fid,)).fetchone()
            if not f:
                continue
            local = now.astimezone(ZoneInfo(f["tz"] or "Europe/Madrid"))
            if not DIGEST_FROM <= local.hour < DIGEST_UNTIL:
                continue
            accounts = [u for u in users.family_users(con, fid) if u.mail_digest]
            docs = {c: store.all_of(con, fid, c) for c in ("members", "events", "tasks", "meals", "lists", "items")}
        today = local.date()
        for u in accounts:
            if not _once(f"digest:{u.id}:{today.isoformat()}"):
                continue
            built = digest_html(docs, today, u.member_id)
            if not built:
                continue
            subject, paras = built
            off = emails.unsubscribe_link(u.id, "resumen")
            mailer.send_later(u.email, subject, mailer.page(f"Hoy, {long_day(today)}", paras, ("Abrir Mam-IA", f"{emails.base()}/app"),
                              foot=emails.unsubscribe_foot(off, "el resumen del día por correo")), unsubscribe=off)
            sent += 1
    return sent


# ---------- the subscription ----------

def _owner(con, fid: int):
    f = con.execute("SELECT name, owner_id FROM families WHERE id=?", (fid,)).fetchone()
    if not f:
        return None, None
    u = users.get_user(con, f["owner_id"]) if f["owner_id"] else None
    if u is None:
        u = next((x for x in users.family_users(con, fid) if x.role == "admin"), None)
    return f["name"], u


def billing(now_ms: int | None = None) -> dict:
    """Notices of the families with a free access or a subscription: the access ends in 7 days and tomorrow, the
    family has become read-only, a payment failed."""
    now_ms = now_ms or int(time.time() * 1000)
    out = {"ending": 0, "readOnly": 0, "failed": 0}
    with db.ro() as con:
        ids = [r[0] for r in con.execute("SELECT family_id FROM grants UNION SELECT family_id FROM stripe_subs UNION SELECT family_id FROM play_subs")]
    for fid in ids:
        try:
            lapsed = status.expired(fid)
        except Exception:   # noqa: BLE001 — Stripe down: next time
            log.exception("could not check the subscription of family %s", fid)
            continue
        with db.ro() as con:
            fam_name, owner = _owner(con, fid)
            g = con.execute("SELECT * FROM grants WHERE family_id=?", (fid,)).fetchone()
            w = con.execute("SELECT * FROM stripe_subs WHERE family_id=?", (fid,)).fetchone()
            pl = con.execute("SELECT expiry_ms FROM play_subs WHERE family_id=?", (fid,)).fetchone()
        if owner is None:
            continue
        if lapsed:
            status.mark_lapse(fid)
            with db.tx() as con:
                first = con.execute("UPDATE lapses SET notified=1 WHERE family_id=? AND notified=0", (fid,)).rowcount
            if first:
                emails.read_only(owner, fam_name)
                out["readOnly"] += 1
            continue
        with db.tx() as con:   # it can write again (renewed, a new code…): a later lapse is a new one
            con.execute("DELETE FROM lapses WHERE family_id=?", (fid,))
        paying = (w is not None and w["status"] in stripe_api.ACTIVE) or (pl is not None and pl["expiry_ms"] > now_ms)
        if g is not None and g["until_ms"] and codes.active(g) and not paying:
            days = math.ceil((g["until_ms"] - now_ms) / 86400000)
            due = [s for s in ENDING_DAYS if days <= s]
            if due and _once(f"ending:{fid}:{g['until_ms']}:{min(due)}"):
                for s in due:   # the earlier notices are not sent late
                    _once(f"ending:{fid}:{g['until_ms']}:{s}")
                emails.access_ending(owner, fam_name, g["until_ms"], days)
                out["ending"] += 1
        if w is not None and w["status"] in ("past_due", "unpaid") and _once(f"failed:{fid}:{w['period_end_ms']}"):
            emails.payment_failed(owner, fam_name)
            out["failed"] += 1
    with db.tx() as con:
        con.execute("DELETE FROM mail_sent WHERE sent_at < ?",
                    ((datetime.now(timezone.utc) - timedelta(days=400)).isoformat(timespec="seconds"),))
    return out


_last_billing = 0.0


def tick(now: datetime) -> None:
    """Called every minute by the reminders' loop."""
    global _last_billing
    digests(now)
    if time.time() - _last_billing >= BILLING_EVERY and mailer.configured():
        _last_billing = time.time()
        r = billing()
        if any(r.values()):
            log.info("subscription notices: %s", r)
