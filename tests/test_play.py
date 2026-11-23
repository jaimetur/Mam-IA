"""Google Play: the family's subscription bought in the Android app (Google is simulated), Administración → Google Play,
and the Android download the landing page offers."""
import json
import time

import pytest

from conftest import confirm, mails_to

SA = {"type": "service_account", "client_email": "mamia@proyecto.iam.gserviceaccount.com",
      "private_key": "-----BEGIN PRIVATE KEY-----\nxxx\n-----END PRIVATE KEY-----\n", "token_uri": "https://oauth2.test/token"}


@pytest.fixture()
def google(server, monkeypatch):
    """Google Play's answers for the purchase tokens: {token: info}."""
    from app.billing import play
    from app.core import crypto, db
    with db.tx() as con:
        db.set_setting(con, "play", {"package": "app.mamia.android", "product": "mamia", "sa": crypto.encrypt(SA)})
    answers, acks, cancels = {}, [], []

    def check(token):
        if token not in answers:
            raise play.PlayError("Google Play no reconoce esa compra.")
        return dict(answers[token])
    monkeypatch.setattr(play, "check", check)
    monkeypatch.setattr(play, "acknowledge", lambda token, product: acks.append(token))
    monkeypatch.setattr(play, "cancel", lambda token, product: cancels.append(token))
    return answers, acks, cancels


def _active(plan="yearly", days=7):
    return {"active": True, "state": "SUBSCRIPTION_STATE_ACTIVE", "product": "mamia", "basePlan": plan,
            "expiry": int((time.time() + days * 86400) * 1000), "acknowledged": False}


def test_config_and_admin(client, server, monkeypatch, new_client):
    assert client.get("/api/play/config").json()["enabled"] is False
    monkeypatch.setenv("MAMIA_ADMIN_EMAIL", "jaime@jtgcloud.test")
    monkeypatch.setenv("MAMIA_ADMIN_PASSWORD", "temporal-123")
    from app.core import config
    config.reload_settings()
    a = new_client()
    a.post("/api/login", json={"email": "jaime@jtgcloud.test", "password": "temporal-123"})
    assert a.put("/api/admin/play", json={"serviceAccount": "no es json"}).status_code == 400
    assert a.put("/api/admin/play", json={"serviceAccount": json.dumps({"client_email": "x"})}).status_code == 400
    assert a.put("/api/admin/play", json={"storeUrl": "https://evil.test/app"}).status_code == 400
    g = a.put("/api/admin/play", json={"serviceAccount": json.dumps(SA), "storeUrl": "https://play.google.com/store/apps/details?id=app.mamia.android"}).json()
    assert g["configured"] and g["serviceAccount"] == SA["client_email"] and g["package"] == "app.mamia.android" and g["product"] == "mamia"
    from app.core import db
    assert "PRIVATE KEY" not in json.dumps(db.get_setting("play"))           # kept encrypted
    c = client.get("/api/play/config").json()
    assert c["enabled"] and c["storeUrl"].startswith("https://play.google.com/")
    assert not a.put("/api/admin/play", json={"remove": True}).json()["configured"]


def _paid_server(monkeypatch):
    monkeypatch.setenv("OPEN_SIGNUP", "0")      # the tests' server lets families in free; here they pay
    from app.core import config
    config.reload_settings()


def test_signup_in_the_app_with_google_play(client, google, monkeypatch):
    _paid_server(monkeypatch)
    answers, acks, _ = google
    r = client.post("/api/web/signup", json={"plan": "monthly", "name": "Ana", "email": "ana@x.test", "password": "secreto-largo",
                                             "family": "Los Ruiz", "store": "play"})
    assert r.status_code == 200
    done = confirm(client, r.json(), "ana@x.test")                         # the email first, as always
    assert done["play"] and done["plan"] == "monthly" and client.get("/api/me").status_code == 401
    assert client.post("/api/play/complete", json={"pending": done["pending"], "token": "falso"}).status_code == 400
    answers["tok-1"] = _active("monthly")
    assert client.post("/api/play/complete", json={"pending": done["pending"], "token": "tok-1"}).json()["signedIn"]
    me = client.get("/api/me").json()
    assert me["family"]["name"] == "Los Ruiz" and me["billing"]["plan"] == "play" and me["billing"]["active"]
    assert acks == ["tok-1"] and mails_to("ana@x.test")[-1]["subject"].endswith("Ya tenéis Mam-IA")
    # the same purchase cannot make another family, nor be used twice
    assert client.post("/api/play/complete", json={"pending": done["pending"], "token": "tok-1"}).status_code == 400


def test_play_signup_needs_google_play_configured(client, monkeypatch):
    _paid_server(monkeypatch)
    r = client.post("/api/web/signup", json={"plan": "yearly", "name": "Ana", "email": "ana@x.test", "password": "secreto-largo", "store": "play"})
    assert r.status_code == 503


def test_expiry_renewal_restore_and_cancel(client, family, google):
    answers, acks, cancels = google
    from app.core import db
    fid = family["user"]["familyId"]
    answers["tok-2"] = _active()
    assert client.post("/api/play/link", json={"token": "tok-2"}).json()["plan"] == "play"
    # over: read-only, and Google is asked again (at most hourly) in case it was renewed
    answers["tok-2"] = {**_active(), "active": False, "state": "SUBSCRIPTION_STATE_EXPIRED", "expiry": int(time.time() * 1000) - 1000}
    with db.tx() as con:
        con.execute("UPDATE play_subs SET expiry_ms=?, checked_at=0 WHERE family_id=?", (int(time.time() * 1000) - 1000, fid))
    assert client.get("/api/me").json()["billing"]["readOnly"]
    answers["tok-2"] = _active()                                             # renewed in Google Play
    with db.tx() as con:
        con.execute("UPDATE play_subs SET checked_at=0 WHERE family_id=?", (fid,))
    assert not client.get("/api/me").json()["billing"]["readOnly"]
    answers["tok-2"] = {**_active(), "state": "SUBSCRIPTION_STATE_CANCELED"}
    b = client.post("/api/play/cancel").json()
    assert cancels == ["tok-2"] and b["cancelAtEnd"] and b["active"]


def test_another_familys_purchase_is_refused(client, family, google, new_client):
    from conftest import signup
    answers, _, _ = google
    answers["tok-3"] = _active()
    client.post("/api/play/link", json={"token": "tok-3"})
    other = new_client()
    signup(other, email="eva@otra.test", name="Eva", family="Otra")
    assert other.post("/api/play/link", json={"token": "tok-3"}).status_code == 400


def test_android_download_for_the_landing(client, server):
    assert client.get("/api/android").json() == {"available": False}
    d = server.data_dir / "android"
    d.mkdir(parents=True)
    (d / "mamia-android.apk").write_bytes(b"PK" + b"0" * 2048)
    (d / "android-build.txt").write_text("build 12 · abc1234\nrelease key · SHA-256 AA:BB\n")
    a = client.get("/api/android").json()
    assert a == {"available": True, "url": "/android.apk", "size": 2050, "build": "build 12 · abc1234"}
    r = client.get("/android.apk")
    assert r.status_code == 200 and r.headers["content-type"] == "application/vnd.android.package-archive"
