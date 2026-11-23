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
    for k in ("MAMIA_ADMIN_EMAIL", "SMTP_HOST", "SECRET_KEY", "MAMIA_REVISION"):
        monkeypatch.delenv(k, raising=False)
    from app.core import config, crypto
    from app.core.security import login_throttle, mail_throttle
    config.reload_settings()
    crypto.reset()
    login_throttle.clear()
    mail_throttle.clear()
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


def signup(c, email="laura@familia.test", name="Laura", family="Familia García", code="", password="secreto-largo"):
    r = c.post("/api/web/signup", json={"plan": "yearly", "name": name, "email": email, "password": password,
                                         "family": family, "code": code})
    assert r.status_code == 200, r.text
    return c.get("/api/me").json()


@pytest.fixture()
def family(client):
    """A signed-up family (Laura, its owner) on the client."""
    return signup(client)
