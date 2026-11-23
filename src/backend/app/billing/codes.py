"""Promotion and invitation codes: a family that signs up with one gets free access for the code's time (1, 3 or 6
months, a year, until a date, or for life); a server administrator can change the end date later (Administración →
Familias). The codes are set in Administración; by default LANZAMIENTO (alias LAUNCH): a year free for the first 50
families, shown on the landing page. A code may have an expiry date and a maximum number of families: after that day,
or once that many families have used it, it is deleted and no longer valid, but the families made with it keep their
free time. A code marked "public" is shown on the landing page as a promotion, with the places it has left. Codes are
compared without accents, case or spaces. Adapted from BodyLens."""
from __future__ import annotations

import time
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core import db

DEFAULT = [{"code": "LANZAMIENTO", "aliases": ["LAUNCH"], "duration": "1y", "expires": "", "max": 50, "used": 0,
            "public": True}]
DURATIONS = ("1m", "3m", "6m", "1y", "life")      # or a date "YYYY-MM-DD": free until the end of that day
TZ = ZoneInfo("Europe/Madrid")


def norm(code: str) -> str:
    s = unicodedata.normalize("NFKD", code or "")
    return "".join(c for c in s if not unicodedata.combining(c) and not c.isspace()).upper()


def clean_duration(d: str) -> str | None:
    """The duration as stored, or None if it is not one."""
    d = (d or "").strip().lower()
    if d in DURATIONS:
        return d
    try:
        return datetime.strptime(d, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def clean_expiry(day: str) -> str | None:
    """An expiry date as stored (YYYY-MM-DD), "" for none, or None if it is not a date."""
    day = (day or "").strip()
    if not day:
        return ""
    try:
        return datetime.strptime(day, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def expired(c: dict, now: float | None = None) -> bool:
    """The code's expiry date has passed (it is valid until the end of that day in Europe/Madrid)."""
    if not c.get("expires"):
        return False
    return c["expires"] < datetime.fromtimestamp(now if now is not None else time.time(), TZ).date().isoformat()


def codes() -> list[dict]:
    """Each code with its duration and expiry date (a plain code, as stored by older versions, is for life and does
    not expire). Expired codes are deleted."""
    s = db.get_setting("codes", None)
    if not isinstance(s, list):
        return [dict(c) for c in DEFAULT]
    out = [{"expires": "", "max": None, "used": 0, "public": False, "aliases": [], **c} if isinstance(c, dict) else
           {"code": c, "duration": "life", "expires": "", "max": None, "used": 0, "public": False, "aliases": []} for c in s]
    keep = [c for c in out if not expired(c)]
    if len(keep) < len(out):
        with db.tx() as con:
            db.set_setting(con, "codes", keep)
    return keep


def find(code: str) -> dict | None:
    n = norm(code)
    return next((c for c in codes() if n and n in names(c)), None)


def names(c: dict) -> set[str]:
    """The code and its aliases, normalised."""
    return {norm(x) for x in [c["code"], *(c.get("aliases") or [])]}


def valid(code: str) -> bool:
    return find(code) is not None


def _add_months(d, months: int):
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):     # the same day of the month, or the last one if that month is shorter
        try:
            return d.replace(year=y, month=m, day=day)
        except ValueError:
            continue


def until_ms(duration: str, now: float | None = None) -> int | None:
    """End of the free access given by a code used now: the end of that day in Europe/Madrid; None = for life."""
    d = clean_duration(duration) or "life"
    if d == "life":
        return None
    today = datetime.fromtimestamp(now if now is not None else time.time(), TZ).date()
    if "-" in d:                            # until a given day (YYYY-MM-DD)
        end = datetime.strptime(d, "%Y-%m-%d").date()
    else:
        end = _add_months(today, {"1m": 1, "3m": 3, "6m": 6, "1y": 12}[d])
    return int(datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=TZ).timestamp() * 1000)


def use(con, code: str) -> dict | None:
    """Counts one more family made with the code, inside the sign-up's transaction: the code (as it was), or None if
    it is not valid or has no places left. A code that reaches its maximum is deleted."""
    import json
    row = con.execute("SELECT value FROM settings WHERE key='codes'").fetchone()
    stored = json.loads(row["value"]) if row else [dict(c) for c in DEFAULT]
    n = norm(code)
    for i, c in enumerate(stored):
        c = {"expires": "", "max": None, "used": 0, "public": False, "aliases": [], **c} if isinstance(c, dict) else \
            {"code": c, "duration": "life", "expires": "", "max": None, "used": 0, "public": False, "aliases": []}
        if not n or n not in names(c) or expired(c):
            continue
        if c["max"] is not None and c["used"] >= c["max"]:
            return None
        c["used"] += 1
        stored[i] = c
        if c["max"] is not None and c["used"] >= c["max"]:
            del stored[i]                    # full: no longer valid
        db.set_setting(con, "codes", stored)
        return c
    return None


def promos() -> list[dict]:
    """The public codes, for the landing page: the code, its duration, its expiry date and the places left."""
    return [{"code": c["code"], "aliases": c.get("aliases") or [], "duration": c["duration"], "expires": c["expires"], "max": c["max"],
             "left": None if c["max"] is None else max(0, c["max"] - c["used"])} for c in codes() if c.get("public")]


def grant(con, family_id: int, code: str | None, until_ms: int | None) -> None:
    con.execute("INSERT INTO grants(family_id, code, until_ms, created_at) VALUES(?,?,?,datetime('now')) "
                "ON CONFLICT(family_id) DO UPDATE SET until_ms=excluded.until_ms, code=coalesce(excluded.code, grants.code)",
                (family_id, code, until_ms))


def active(row) -> bool:
    return row["until_ms"] is None or row["until_ms"] > time.time() * 1000
