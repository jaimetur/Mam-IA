"""Repetitions of events and tasks, and the reminders they produce. The web app has the same rules in
src/frontend/app/js/dates.js (both are tested with the same cases): keep them in step.

A repetition is {"freq": "daily"|"weekly"|"monthly"|"yearly", "every": N, "days": [0..6] (weekly, Monday = 0),
"until": "YYYY-MM-DD"}; "exdates" of an event are the days skipped."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ALL_DAY_HOUR = 9   # reminders of all-day events and of tasks without a time are counted from 09:00


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def occurs_on(start: date, rule: dict | None, day: date) -> bool:
    """Whether something that starts on `start` with the repetition `rule` happens on `day`."""
    if day < start:
        return False
    if not rule:
        return day == start
    until = rule.get("until")
    if until and day > _d(until):
        return False
    every = max(1, int(rule.get("every") or 1))
    freq = rule.get("freq")
    if freq == "daily":
        return (day - start).days % every == 0
    if freq == "weekly":
        days = rule.get("days") or [start.weekday()]
        if day.weekday() not in days:
            return False
        week0 = start - timedelta(days=start.weekday())
        return ((day - week0).days // 7) % every == 0
    if freq == "monthly":
        months = (day.year - start.year) * 12 + day.month - start.month
        return day.day == start.day and months % every == 0
    if freq == "yearly":
        return day.month == start.month and day.day == start.day and (day.year - start.year) % every == 0
    return False


def occurrences(start: date, rule: dict | None, first: date, last: date, skip: set[str] | None = None) -> list[date]:
    """The days between `first` and `last` (both included) on which it happens."""
    out, d = [], max(first, start)
    while d <= last:
        if occurs_on(start, rule, d) and (not skip or d.isoformat() not in skip):
            out.append(d)
        d += timedelta(days=1)
    return out


def _local(day: date, hhmm: str | None, tz: ZoneInfo) -> datetime:
    h, m = (int(x) for x in hhmm.split(":")) if hhmm else (ALL_DAY_HOUR, 0)
    return datetime.combine(day, time(h, m), tzinfo=tz)


def alarms(docs: dict[str, dict[str, dict]], tz_name: str, t0: datetime, t1: datetime) -> list[dict]:
    """The reminders of the family that go off between t0 (excluded) and t1 (included).
    `docs` is {collection: {id: data}}. Each reminder: id, at (aware datetime), title, body, who (member ids), path."""
    tz = ZoneInfo(tz_name or "Europe/Madrid")
    members = docs.get("members", {})
    name = lambda mid: (members.get(mid) or {}).get("name", "")   # noqa: E731
    out = []
    lo, hi = t0.astimezone(tz).date() - timedelta(days=15), t1.astimezone(tz).date() + timedelta(days=15)
    for eid, e in docs.get("events", {}).items():
        if e.get("remind") is None or not e.get("start"):
            continue
        start = _d(e["start"])
        hhmm = None if e.get("allDay") or len(e["start"]) == 10 else e["start"][11:16]
        for day in occurrences(start, e.get("repeat"), lo, hi, set(e.get("exdates") or [])):
            at = _local(day, hhmm, tz) - timedelta(minutes=e["remind"])
            if t0 < at <= t1:
                bits = [hhmm or "Todo el día"]
                if e.get("driver"):
                    bits.append(f"lleva {name(e['driver'])}")
                if e.get("pickup"):
                    bits.append(f"recoge {name(e['pickup'])}")
                if e.get("place"):
                    bits.append(e["place"])
                who = [w for w in (e.get("who") or []) if name(w)]
                title = e["title"] + (" · " + ", ".join(name(w) for w in who) if who else "")
                out.append({"id": f"ev:{eid}:{day.isoformat()}", "at": at, "title": title, "body": " · ".join(bits),
                            "who": list(dict.fromkeys([*who, *(x for x in (e.get("driver"), e.get("pickup")) if x)])),
                            "path": "/app#agenda"})
    for tid, t in docs.get("tasks", {}).items():
        if t.get("remind") is None or t.get("done") or not t.get("due"):
            continue
        at = _local(_d(t["due"]), t.get("time"), tz) - timedelta(minutes=t["remind"])
        if t0 < at <= t1:
            body = (t.get("time") or "Hoy") + (f" · {name(t['who'])}" if t.get("who") and name(t["who"]) else "")
            out.append({"id": f"tk:{tid}:{t['due']}", "at": at, "title": t["title"], "body": body,
                        "who": [t["who"]] if t.get("who") else [], "path": "/app#tareas"})
    return out
