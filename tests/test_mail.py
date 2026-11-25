"""Email: the confirmation code to sign up, change the address or join a family, the reminders and the summary of the
day by email, the notices of the subscription, unsubscribing and Administración → Correo."""
import json
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from conftest import code_for, confirm, mails_to, signup

TZ = ZoneInfo("Europe/Madrid")


def _start(c, email="ana@x.test", code=""):
    return c.post("/api/web/signup", json={"name": "Ana", "email": email, "password": "secreto-largo", "family": "Los Ruiz",
                                            "code": code})


def test_signup_needs_the_emailed_code(client, outbox):
    r = _start(client)
    assert r.status_code == 200 and r.json()["email"] == "ana@x.test"
    started = r.json()
    assert client.get("/api/me").status_code == 401                 # nothing is made before the code
    from app.core import db
    with db.ro() as con:
        assert con.execute("SELECT count(*) FROM families").fetchone()[0] == 0
    assert "Tu código es" in outbox[-1]["subject"] and outbox[-1]["to"] == "ana@x.test"
    wrong = "000000" if code_for("ana@x.test") != "000000" else "111111"
    bad = client.post("/api/web/verify", json={"id": started["verify"], "code": wrong})
    assert bad.status_code == 400 and "4 intentos" in bad.json()["detail"]
    # a new code is not sent straight away
    assert "Espera" in client.post("/api/web/verify/resend", json={"id": started["verify"]}).json()["detail"]
    assert confirm(client, started, "ana@x.test")["signedIn"]
    me = client.get("/api/me").json()
    assert me["family"]["name"] == "Los Ruiz" and me["user"]["email"] == "ana@x.test"
    assert outbox[-1]["subject"].endswith("Ya tenéis Mam-IA")
    # the same code cannot be used twice
    assert client.post("/api/web/verify", json={"id": started["verify"], "code": code_for("ana@x.test")}).status_code == 400


def test_wrong_codes_and_expired_codes(client, monkeypatch):
    started = _start(client).json()
    for _ in range(4):
        client.post("/api/web/verify", json={"id": started["verify"], "code": "abc"})
    r = client.post("/api/web/verify", json={"id": started["verify"], "code": "abc"})
    assert r.status_code == 400 and "demasiadas veces" in r.json()["detail"]
    assert client.post("/api/web/verify", json={"id": started["verify"], "code": code_for("ana@x.test")}).status_code == 400
    # a code is valid for 30 minutes; after a minute another one can be asked for
    started = _start(client).json()
    from app.accounts import verify
    later = time.time() + 31 * 60
    monkeypatch.setattr(verify.time, "time", lambda: later)
    r = client.post("/api/web/verify", json={"id": started["verify"], "code": code_for("ana@x.test")})
    assert r.status_code == 400 and "caducado" in r.json()["detail"]
    n = len(mails_to("ana@x.test"))
    assert client.post("/api/web/verify/resend", json={"id": started["verify"]}).status_code == 200
    assert len(mails_to("ana@x.test")) == n + 1                      # a new code, valid from now
    monkeypatch.setattr(verify.time, "time", lambda: later + 5)
    assert confirm(client, started, "ana@x.test")["signedIn"]


def test_signup_is_closed_without_mail_and_bad_codes_send_nothing(client, outbox, monkeypatch):
    r = _start(client, code="NO-EXISTE")
    assert r.status_code == 400 and "código" in r.json()["detail"] and not outbox
    monkeypatch.setenv("SMTP_HOST", "")
    r = _start(client)
    assert r.status_code == 400 and "correo" in r.json()["detail"]


def test_new_family_notice_to_the_server_admins(server, monkeypatch, new_client):
    monkeypatch.setenv("MAMIA_ADMIN_EMAIL", "jaime@jtgcloud.test")
    from app.core import config
    config.reload_settings()
    c = new_client()
    signup(c, email="ana@x.test", name="Ana", family="Los Ruiz", code="LANZAMIENTO")
    m = mails_to("jaime@jtgcloud.test")[-1]
    # the administrator's account (made from MAMIA_ADMIN_EMAIL) has no language chosen: English
    assert m["subject"].startswith("Mam-IA · New family: ") and "Ruiz" in m["subject"] and "LANZAMIENTO" in m["text"]


def test_change_email_with_a_code(client, family, new_client):
    assert client.put("/api/me", json={"email": "nuevo@familia.test"}).status_code == 400
    assert client.post("/api/me/email", json={"email": "nuevo@familia.test", "password": "mal"}).status_code == 400
    r = client.post("/api/me/email", json={"email": "nuevo@familia.test", "password": "secreto-largo"})
    assert r.status_code == 200
    assert client.get("/api/me").json()["user"]["email"] == "laura@familia.test"   # not until the code
    assert confirm(client, r.json(), "nuevo@familia.test")["user"]["email"] == "nuevo@familia.test"
    assert "El correo de tu cuenta ha cambiado" in mails_to("laura@familia.test")[-1]["subject"]
    other = new_client()
    assert other.post("/api/login", json={"email": "nuevo@familia.test", "password": "secreto-largo"}).status_code == 200


def _event_soon(client, **extra):
    now = datetime.now(TZ).replace(second=0, microsecond=0)
    start = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
    client.post("/api/sync", json={"changes": [{"c": "events", "id": "e1", "data": {"title": "Pediatra", "start": start, "remind": 30, **extra}}]})
    return now


def test_reminders_by_email_go_to_who_it_concerns(client, family, new_client, outbox):
    r = client.post("/api/family/invites", json={})
    code = r.json()["link"].split("c=")[1]
    pablo = new_client()
    started = pablo.post("/api/invites/accept", json={"code": code, "name": "Pablo", "email": "pablo@familia.test", "password": "secreto-pablo"}).json()
    confirm(pablo, started, "pablo@familia.test")
    pm = pablo.get("/api/me").json()["user"]["memberId"]
    now = _event_soon(client, who=[pm])
    from app.push.routes import due_now
    outbox.clear()
    assert due_now(now - timedelta(minutes=1), now + timedelta(minutes=1)) == 1
    assert [m["to"] for m in outbox] == ["pablo@familia.test"]
    m = outbox[0]
    assert "Pediatra" in m["subject"] and "Hoy" in m["text"] and m["unsubscribe"].startswith("<https://mamia.test/correo/baja?")
    # Pablo does not want them: nobody gets them (not Laura instead)
    assert pablo.put("/api/me", json={"mailReminders": False}).json()["user"]["mailReminders"] is False
    client.post("/api/sync", json={"changes": [{"c": "events", "id": "e2", "data": {"title": "Fútbol", "start": (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M"), "remind": 30, "who": [pm]}}]})
    outbox.clear()
    assert due_now(now - timedelta(minutes=1), now + timedelta(minutes=1)) == 0 and not outbox


def test_task_reminder_email_can_tick_it_off(client, family, outbox):
    now = datetime.now(TZ).replace(second=0, microsecond=0)
    t = now + timedelta(minutes=10)
    client.post("/api/sync", json={"changes": [{"c": "tasks", "id": "t1", "data": {"title": "Pagar el comedor", "due": t.date().isoformat(), "time": t.strftime("%H:%M"), "remind": 10}}]})
    from app.push.routes import due_now
    outbox.clear()
    due_now(now - timedelta(minutes=1), now + timedelta(minutes=1))
    assert f"/app?hecho=tk%3At1%3A{t.date().isoformat()}#tareas" in outbox[-1]["text"]


def test_unsubscribe_link(client, family, outbox):
    _event = _event_soon(client)
    from app.push.routes import due_now
    outbox.clear()
    due_now(_event - timedelta(minutes=1), _event + timedelta(minutes=1))
    link = re.search(r"Dejar de recibirlos: (\S+)", outbox[-1]["text"]).group(1)
    path = link.replace("https://mamia.test", "")
    assert client.get(path.replace("&s=", "&s=x")).text.count("no es válido") == 1
    r = client.get(path)
    assert r.status_code == 200 and "Ya no te enviaremos los recordatorios" in r.text
    assert client.get("/api/me").json()["user"]["mailReminders"] is False
    client.put("/api/me", json={"mailReminders": True})
    assert client.post(path, data={"List-Unsubscribe": "One-Click"}).status_code == 200   # the email apps' button
    assert client.get("/api/me").json()["user"]["mailReminders"] is False


def test_summary_of_the_day(client, family, outbox):
    from app.notices import scheduler
    today = datetime.now(TZ).date()
    me = family["user"]["memberId"]
    client.post("/api/sync", json={"changes": [
        {"c": "events", "id": "e1", "data": {"title": "Natación", "start": f"{today.isoformat()}T17:30", "who": [me]}},
        {"c": "events", "id": "e2", "data": {"title": "Excursión", "start": today.isoformat(), "allDay": True}},
        {"c": "tasks", "id": "t1", "data": {"title": "Comprar regalo", "due": today.isoformat(), "who": me}},
        {"c": "tasks", "id": "t2", "data": {"title": "Llamar al seguro", "due": (today - timedelta(days=2)).isoformat()}},
        {"c": "meals", "id": "m1", "data": {"date": today.isoformat(), "slot": "cena", "dish": "Tortilla"}},
    ]})
    at8 = datetime.combine(today, datetime.min.time(), TZ).replace(hour=8)
    assert scheduler.digests(at8) == 0                               # off unless asked for
    assert client.put("/api/me", json={"mailDigest": True}).json()["user"]["mailDigest"] is True
    assert scheduler.digests(at8.replace(hour=6)) == 0               # not before 07:00
    outbox.clear()
    assert scheduler.digests(at8) == 1 and scheduler.digests(at8) == 0   # once a day
    m = outbox[0]
    assert m["subject"].endswith("Tu día: 2 planes y 1 tarea")
    text = m["text"]
    assert text.index("Todo el día") < text.index("17:30 · Natación")
    assert "Comprar regalo (te toca)" in text and "Pendientes de días anteriores" in text and "Cena: Tortilla" in text


def test_subscription_notices(client, family, outbox):
    from app.billing import codes
    from app.core import db
    from app.notices import scheduler
    fid = family["user"]["familyId"]
    day = 86400000
    now = int(time.time() * 1000)
    with db.tx() as con:
        codes.grant(con, fid, "PRUEBA", now + 5 * day)
    outbox.clear()
    assert scheduler.billing(now)["ending"] == 1 and scheduler.billing(now)["ending"] == 0
    assert "termina dentro de 5 días" in outbox[-1]["subject"]
    assert scheduler.billing(now + 4 * day + 3600000)["ending"] == 1   # and the day before
    assert "termina mañana" in outbox[-1]["subject"]
    with db.tx() as con:   # over: read-only, told once
        con.execute("UPDATE grants SET until_ms=? WHERE family_id=?", (now - 1000, fid))
    assert scheduler.billing()["readOnly"] == 1 and scheduler.billing()["readOnly"] == 0
    assert "solo lectura" in outbox[-1]["subject"]
    with db.tx() as con:   # renewed and over again later: told again
        codes.grant(con, fid, "PRUEBA", now + 400 * day)
    scheduler.billing()
    with db.ro() as con:
        assert con.execute("SELECT count(*) FROM lapses").fetchone()[0] == 0


def test_admin_mail_settings_and_test_email(server, monkeypatch, new_client):
    monkeypatch.setenv("MAMIA_ADMIN_EMAIL", "jaime@jtgcloud.test")
    monkeypatch.setenv("MAMIA_ADMIN_PASSWORD", "temporal-123")
    from app.core import config
    config.reload_settings()
    c = new_client()
    c.post("/api/login", json={"email": "jaime@jtgcloud.test", "password": "temporal-123"})
    assert c.get("/api/admin/mail").json()["logOnly"] is True
    r = c.put("/api/admin/mail", json={"host": "log", "port": 465, "security": "ssl", "username": "mamia@jtgcloud.test",
                                       "password": "clave-smtp", "from_address": "mamia@jtgcloud.test", "from_name": "Mam-IA"})
    s = r.json()
    assert s["hasPassword"] and "password" not in s and s["from_address"] == "mamia@jtgcloud.test"
    from app.core import db
    assert "clave-smtp" not in json.dumps(db.get_setting("mail"))  # kept encrypted
    assert c.post("/api/admin/test-email", json={}).json()["to"] == "jaime@jtgcloud.test"
    assert "Email check" in mails_to("jaime@jtgcloud.test")[-1]["subject"]   # no language chosen: English
    assert c.put("/api/me", json={"lang": "es"}).status_code == 200
    c.post("/api/admin/test-email", json={})
    assert "Comprobación del correo" in mails_to("jaime@jtgcloud.test")[-1]["subject"]
    assert c.put("/api/admin/mail", json={"security": "tls"}).status_code == 400
    assert c.put("/api/admin/mail", json={"remove": True}).json()["from_address"] == "mamia@mamia.test"   # the .env again


def test_old_database_gets_the_new_columns(server):
    import sqlite3

    from app.core import db
    path = server.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT); CREATE TABLE lapses (family_id INTEGER PRIMARY KEY, lapsed_at TEXT);")
    con.close()
    db.init_db()
    with db.ro() as con:
        cols = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
        assert {"mail_reminders", "mail_digest"} <= cols
        assert "notified" in {r["name"] for r in con.execute("PRAGMA table_info(lapses)")}
