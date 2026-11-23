"""Signing up, in and out, the account, passwords, the server administrator and the app's header against CSRF."""
from conftest import signup


def test_signup_makes_family_member_and_lists(client):
    me = signup(client)
    assert me["user"]["role"] == "admin" and me["family"]["name"] == "Familia García"
    assert me["family"]["ownerId"] == me["user"]["id"]
    docs = client.get("/api/sync?since=0").json()["docs"]
    members = [d for d in docs if d["c"] == "members"]
    assert len(members) == 1 and members[0]["data"]["userId"] == me["user"]["id"]
    assert me["user"]["memberId"] == members[0]["id"]
    assert {d["id"] for d in docs if d["c"] == "lists"} == {"super", "farmacia"}
    assert me["billing"] == {"plan": "free", "active": True, "readOnly": False}


def test_login_logout_and_wrong_password(client, family):
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/login", json={"email": "laura@familia.test", "password": "otra-cosa"}).status_code == 401
    r = client.post("/api/login", json={"email": "LAURA@familia.test", "password": "secreto-largo"})
    assert r.status_code == 200 and r.json()["user"]["name"] == "Laura"


def test_login_is_throttled(client, family):
    for _ in range(8):
        client.post("/api/login", json={"email": "laura@familia.test", "password": "mal"})
    assert client.post("/api/login", json={"email": "laura@familia.test", "password": "secreto-largo"}).status_code == 429


def test_duplicate_email_and_short_password(client, family, new_client):
    other = new_client()
    r = other.post("/api/web/signup", json={"name": "X", "email": "laura@familia.test", "password": "secreto-largo"})
    assert r.status_code == 400 and "correo" in r.json()["detail"]
    r = other.post("/api/web/signup", json={"name": "X", "email": "x@familia.test", "password": "corta"})
    assert r.status_code == 400 and "8" in r.json()["detail"]


def test_writes_need_the_app_header(server, family):
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as bare:
        assert bare.post("/api/login", json={"email": "a@b.c", "password": "x"}).status_code == 403


def test_profile_and_password_change(client, family):
    r = client.put("/api/me", json={"name": "Laura G.", "theme": "dark", "accent": "menta"})
    assert r.status_code == 200 and r.json()["user"]["theme"] == "dark"
    assert client.put("/api/me", json={"theme": "neón"}).status_code == 400
    assert client.post("/api/me/password", json={"current": "mal", "new": "nueva-clave-1"}).status_code == 400
    assert client.post("/api/me/password", json={"current": "secreto-largo", "new": "nueva-clave-1"}).status_code == 200
    client.post("/api/logout")
    assert client.post("/api/login", json={"email": "laura@familia.test", "password": "nueva-clave-1"}).status_code == 200


def test_password_reset_with_token(client, family):
    from app.accounts import users
    from app.core import db
    with db.tx() as con:
        token = users.create_reset(con, family["user"]["id"])
    client.post("/api/logout")
    assert client.post("/api/password/reset", json={"token": "nope", "password": "nueva-clave-2"}).status_code == 400
    assert client.post("/api/password/reset", json={"token": token, "password": "nueva-clave-2"}).status_code == 200
    assert client.get("/api/me").status_code == 200   # signed in
    assert client.post("/api/password/reset", json={"token": token, "password": "otra-clave-3"}).status_code == 400


def test_forgot_password_needs_mail(client, family):
    assert client.post("/api/password/forgot", json={"email": "laura@familia.test"}).status_code == 503


def test_bootstrap_admin(server, monkeypatch):
    monkeypatch.setenv("MAMIA_ADMIN_EMAIL", "jaime@jtgcloud.test")
    monkeypatch.setenv("MAMIA_ADMIN_PASSWORD", "temporal-123")
    from app.core import config
    config.reload_settings()
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app, headers={"x-mamia": "1"}) as c:
        r = c.post("/api/login", json={"email": "jaime@jtgcloud.test", "password": "temporal-123"})
        u = r.json()["user"]
        assert u["isAdmin"] and u["mustChange"]
        assert c.get("/app", follow_redirects=False).headers["location"] == "/cuenta?cambiar=1"
        assert c.post("/api/me/password", json={"new": "definitiva-123"}).status_code == 200
        me = c.get("/api/me").json()
        assert me["billing"]["plan"] == "gift" and me["billing"]["expiry"] is None   # free for life
        assert c.get("/api/admin/overview").status_code == 200


def test_delete_own_account_alone_deletes_family(client, family):
    assert client.post("/api/me/delete", json={"password": "mal"}).status_code == 400
    assert client.post("/api/me/delete", json={"password": "secreto-largo"}).status_code == 200
    from app.core import db
    with db.ro() as con:
        assert con.execute("SELECT count(*) FROM families").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM docs").fetchone()[0] == 0
