"""Repetitions and reminders (the same cases as tests/frontend/dates.test.mjs), Web Push and the pages."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.push import recur

TZ = ZoneInfo("Europe/Madrid")
MON = date(2026, 11, 23)


def test_occurrences():
    weekly = {"freq": "weekly", "every": 1, "days": [0, 2]}
    assert recur.occurrences(MON, weekly, MON, MON + timedelta(days=13)) == [
        date(2026, 11, 23), date(2026, 11, 25), date(2026, 11, 30), date(2026, 12, 2)]
    every2 = {"freq": "weekly", "every": 2}
    assert recur.occurrences(MON, every2, MON, MON + timedelta(days=28)) == [MON, date(2026, 12, 7), date(2026, 12, 21)]
    monthly = {"freq": "monthly", "every": 1}
    assert recur.occurrences(date(2026, 1, 31), monthly, date(2026, 1, 1), date(2026, 5, 31)) == [date(2026, 1, 31), date(2026, 3, 31), date(2026, 5, 31)]
    assert recur.occurrences(MON, {"freq": "daily", "every": 1, "until": "2026-11-25"}, MON, MON + timedelta(days=9)) == [
        MON, date(2026, 11, 24), date(2026, 11, 25)]
    assert recur.occurrences(MON, weekly, MON, MON + timedelta(days=6), skip={"2026-11-25"}) == [MON]


def test_alarms_of_events_and_tasks():
    docs = {
        "members": {"mU": {"name": "Lucas"}, "mP": {"name": "Pablo"}},
        "events": {"e1": {"title": "Dentista", "start": "2026-11-26T17:30", "who": ["mU"], "driver": "mP", "remind": 60},
                   "e2": {"title": "Natación", "start": "2026-11-23T16:30", "repeat": {"freq": "weekly", "every": 1, "days": [0, 2]}, "remind": 30},
                   "e3": {"title": "Excursión", "start": "2026-11-27", "allDay": True, "remind": 1440},
                   "e4": {"title": "Sin aviso", "start": "2026-11-26T10:00"}},
        "tasks": {"t1": {"title": "Pagar el comedor", "due": "2026-11-24", "time": "10:00", "remind": 0},
                  "t2": {"title": "Hecha", "due": "2026-11-24", "remind": 0, "done": True}},
    }
    t0 = datetime(2026, 11, 23, 0, 0, tzinfo=TZ)
    got = {a["id"]: a for a in recur.alarms(docs, "Europe/Madrid", t0, t0 + timedelta(days=7))}
    assert set(got) == {"ev:e1:2026-11-26", "ev:e2:2026-11-23", "ev:e2:2026-11-25", "ev:e3:2026-11-27", "tk:t1:2026-11-24"}
    a = got["ev:e1:2026-11-26"]
    assert a["at"] == datetime(2026, 11, 26, 16, 30, tzinfo=TZ) and a["title"] == "Dentista · Lucas"
    assert a["body"] == "17:30 · lleva Pablo" and set(a["who"]) == {"mU", "mP"}
    assert got["ev:e3:2026-11-27"]["at"] == datetime(2026, 11, 26, 9, 0, tzinfo=TZ)   # all day, the day before at 09:00
    assert got["tk:t1:2026-11-24"]["at"] == datetime(2026, 11, 24, 10, 0, tzinfo=TZ)


def test_push_key_subscribe_and_send(client, family, monkeypatch):
    key = client.get("/api/push/key").json()["key"]
    assert len(key) > 80 and client.get("/api/push/key").json()["key"] == key        # made once
    assert client.post("/api/push/subscribe", json={"endpoint": "http://x", "keys": {}}).status_code == 400
    sub = {"endpoint": "https://push.example.test/abc", "keys": {"p256dh": "p", "auth": "a"}}
    assert client.post("/api/push/subscribe", json=sub).status_code == 200
    sent = []
    import pywebpush
    monkeypatch.setattr(pywebpush, "webpush", lambda info, data, **kw: sent.append((info["endpoint"], data)))
    now = datetime.now(TZ).replace(second=0, microsecond=0)
    start = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
    client.post("/api/sync", json={"changes": [{"c": "events", "id": "e1", "data": {"title": "Pediatra", "start": start, "remind": 30}}]})
    from app.core import mailer
    from app.push.routes import due_now
    mailer.SENT.clear()
    assert due_now(now - timedelta(minutes=1), now + timedelta(minutes=1)) == 2       # the phone and the email
    assert due_now(now - timedelta(minutes=1), now + timedelta(minutes=1)) == 0       # never twice
    assert sent[0][0] == sub["endpoint"] and "Pediatra" in sent[0][1]
    assert [m["to"] for m in mailer.SENT] == ["laura@familia.test"] and "Pediatra" in mailer.SENT[0]["subject"]


def test_pages(client, server):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200 and "Mam-IA" in r.text
    assert client.get("/", headers={"user-agent": "x MamIAApp/0.2.1"}, follow_redirects=False).headers["location"] == "/entrar"
    assert client.get("/app?apuntar=hola", follow_redirects=False).headers["location"] == "/entrar?next=%2Fapp%3Fapuntar%3Dhola"
    for p in ("/entrar", "/alta", "/unirse", "/recuperar", "/bienvenida", "/privacidad", "/terminos", "/borrar-cuenta"):
        assert client.get(p).status_code == 200, p
    assert "{{v}}" not in client.get("/entrar").text
    assert client.get("/static/common/tokens.css").status_code == 200
    assert client.get("/static/common/fonts/figtree-latin.woff2").headers["content-type"] == "font/woff2"
    # the brand (assets/branding) at the root of the site
    for name, kind in (("logo.svg", "image/svg+xml"), ("favicon-32.png", "image/png"), ("icon-192.png", "image/png"),
                       ("icon-512.png", "image/png"), ("icon-maskable-512.png", "image/png"), ("apple-touch-icon.png", "image/png")):
        r = client.get(f"/{name}")
        assert r.status_code == 200 and r.headers["content-type"] == kind, name
    assert client.get("/favicon.ico").headers["content-type"] == "image/png"
    assert client.get("/static/common/logo.svg").status_code == 404
    icons = [i["src"] for i in client.get("/manifest.webmanifest").json()["icons"]]
    assert all(client.get(src).status_code == 200 for src in icons)
    assert client.get("/static/../pyproject.toml").status_code == 404
    assert client.get("/static/app/index.html").status_code == 404
    sw = client.get("/sw.js")
    assert sw.headers["service-worker-allowed"] == "/" and "{{v}}" not in sw.text
    assert "unregister" in client.get("/service-worker.js").text
    assert client.get("/manifest.webmanifest").json()["start_url"] == "/app"
    assert client.get("/android.apk", follow_redirects=False).status_code == 302


def test_signed_in_pages(client, family):
    assert client.get("/", follow_redirects=False).headers["location"] == "/app"
    assert client.get("/app").status_code == 200
    assert client.get("/cuenta").status_code == 200
    assert client.get("/admin", follow_redirects=False).headers["location"] == "/app"
