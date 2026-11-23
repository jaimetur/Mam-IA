"""A fresh server (empty database in a temporary folder) for each test, and helpers to sign up and call the API."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("COOKIE_SECURE", "0")
    monkeypatch.setenv("SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("OPEN_SIGNUP", "1")
    # emails are not sent: they are kept in mailer.SENT (see the outbox fixture)
    monkeypatch.setenv("SMTP_HOST", "log")
    monkeypatch.setenv("SMTP_FROM", "mamia@mamia.test")
    monkeypatch.setenv("PUBLIC_URL", "https://mamia.test")
    for k in ("MAMIA_ADMIN_EMAIL", "SECRET_KEY", "MAMIA_REVISION"):
        monkeypatch.delenv(k, raising=False)
    from app.core import config, crypto, mailer
    from app.core.security import login_throttle, mail_throttle
    config.reload_settings()
    crypto.reset()
    login_throttle.clear()
    mail_throttle.clear()
    mailer.SENT.clear()
    yield config.settings
    crypto.reset()


@pytest.fixture()
def client(server):
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app, headers={"x-mamia": "1"}) as c:
        yield c


@pytest.fixture()
def new_client(server):
    """Another device (its own cookies), for a second person of the family."""
    from fastapi.testclient import TestClient

    from app.main import app
    clients = []

    def make():
        c = TestClient(app, headers={"x-mamia": "1"})
        c.__enter__()
        clients.append(c)
        return c
    yield make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture()
def outbox(server):
    """The emails sent during the test: [{to, subject, text, unsubscribe}]."""
    from app.core import mailer
    return mailer.SENT


def mails_to(email):
    from app.core import mailer
    return [m for m in mailer.SENT if email.lower() in m["to"].lower()]


def code_for(email):
    """The last confirmation code emailed to an address."""
    import re
    for m in reversed(mails_to(email)):
        found = re.search(r"Tu código es (\d{6})", m["subject"])
        if found:
            return found.group(1)
    raise AssertionError(f"no code was emailed to {email}")


def confirm(c, started, email):
    """Write the emailed code of a pending confirmation ({verify: id} from the API)."""
    r = c.post("/api/web/verify", json={"id": started["verify"], "code": code_for(email)})
    assert r.status_code == 200, r.text
    return r.json()


def signup(c, email="laura@familia.test", name="Laura", family="Familia García", code="", password="secreto-largo"):
    r = c.post("/api/web/signup", json={"plan": "yearly", "name": name, "email": email, "password": password,
                                         "family": family, "code": code})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == email
    assert confirm(c, r.json(), email)["signedIn"]
    return c.get("/api/me").json()


@pytest.fixture()
def family(client):
    """A signed-up family (Laura, its owner) on the client."""
    return signup(client)
