"""The launch promotion, read-only families, Stripe's sign-up (with Stripe mocked) and Administración."""
import hashlib
import hmac
import json
import time

from conftest import signup


def test_launch_promo_gives_a_year_and_counts_places(client, monkeypatch):
    assert client.get("/api/promos").json()["promos"][0] == {"code": "LANZAMIENTO", "aliases": ["LAUNCH"], "duration": "1y",
                                                             "expires": "", "max": 50, "left": 50}
    me = signup(client, code=" lanzamiento ")
    b = me["billing"]
    assert b["plan"] == "gift" and b["active"] and b["code"] == "LANZAMIENTO"
    assert 360 * 86400000 < b["expiry"] - time.time() * 1000 < 367 * 86400000
    assert client.get("/api/promos").json()["promos"][0]["left"] == 49


def test_promo_runs_out(client, new_client):
    from app.core import db
    with db.tx() as con:
        db.set_setting(con, "codes", [{"code": "LANZAMIENTO", "aliases": [], "duration": "1y", "expires": "", "max": 1, "used": 0, "public": True}])
    signup(client, code="LANZAMIENTO")
    other = new_client()
    r = other.post("/api/web/signup", json={"name": "Ana", "email": "ana@x.test", "password": "secreto-largo", "code": "LANZAMIENTO"})
    assert r.status_code == 400
    assert client.get("/api/promos").json()["promos"] == []


def test_expired_family_is_read_only(client, family):
    from app.billing import codes
    from app.core import db
    with db.tx() as con:
        codes.grant(con, family["user"]["familyId"], "PRUEBA", int(time.time() * 1000) - 1000)
    r = client.post("/api/sync", json={"changes": [{"c": "tasks", "id": "t1", "data": {"title": "x"}}]})
    assert r.status_code == 402
    assert client.get("/api/sync?since=0").status_code == 200         # still readable
    assert client.get("/api/family/export").status_code == 200         # and exportable
    me = client.get("/api/me").json()
    assert me["billing"]["readOnly"] and me["billing"]["lapsedAt"]


def test_paid_signup_without_stripe(client, server, monkeypatch):
    monkeypatch.setenv("OPEN_SIGNUP", "0")
    from app.core import config
    config.reload_settings()
    r = client.post("/api/web/signup", json={"name": "Ana", "email": "ana@x.test", "password": "secreto-largo"})
    assert r.status_code == 503


def _sign(secret: str, payload: bytes) -> str:
    t = str(int(time.time()))
    return f"t={t},v1=" + hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()


def test_stripe_checkout_creates_the_family(client, server, monkeypatch):
    from app.billing import stripe
    from app.core import crypto, db
    monkeypatch.setenv("OPEN_SIGNUP", "0")
    from app.core import config
    config.reload_settings()
    with db.tx() as con:
        db.set_setting(con, "stripe", {"secret": crypto.encrypt("sk_test_x"), "webhook": crypto.encrypt("whsec_x"),
                                       "prices": {"monthly": "price_m", "yearly": "price_y"}})
    calls = []

    def fake_call(method, path, params=None, secret=None):
        calls.append((method, path, params))
        if path == "/checkout/sessions":
            return {"url": "https://checkout.stripe.test/s"}
        raise AssertionError(path)
    monkeypatch.setattr(stripe, "call", fake_call)
    r = client.post("/api/web/signup", json={"plan": "monthly", "name": "Ana", "email": "ana@x.test", "password": "secreto-largo", "family": "Los Ruiz"})
    assert r.json()["url"] == "https://checkout.stripe.test/s"
    params = calls[0][2]
    assert params["line_items"][0]["price"] == "price_m" and params["subscription_data"]["trial_period_days"] == 7
    pending = params["metadata"]["pending"]
    sub = {"id": "sub_1", "customer": "cus_1", "status": "trialing", "current_period_end": int(time.time()) + 7 * 86400,
           "items": {"data": [{"price": {"id": "price_m"}}]}, "default_payment_method": {"card": {"brand": "visa", "last4": "4242"}}}
    event = {"type": "checkout.session.completed", "data": {"object": {"status": "complete", "subscription": sub, "metadata": {"pending": pending}}}}
    payload = json.dumps(event).encode()
    assert client.post("/api/web/webhook", content=payload, headers={"stripe-signature": "t=1,v1=bad"}).status_code == 400
    assert client.post("/api/web/webhook", content=payload, headers={"stripe-signature": _sign("whsec_x", payload)}).status_code == 200
    assert client.post("/api/login", json={"email": "ana@x.test", "password": "secreto-largo"}).status_code == 200
    me = client.get("/api/me").json()
    assert me["family"]["name"] == "Los Ruiz"
    assert me["billing"]["plan"] == "web" and me["billing"]["active"] and me["billing"]["method"] == "Visa ·4242"
    # a later cancellation from Stripe makes the family read-only
    sub2 = {**sub, "status": "canceled"}
    ev2 = json.dumps({"type": "customer.subscription.deleted", "data": {"object": sub2}}).encode()
    client.post("/api/web/webhook", content=ev2, headers={"stripe-signature": _sign("whsec_x", ev2)})
    assert client.get("/api/me").json()["billing"]["readOnly"]


def test_admin_codes_and_grants(server, monkeypatch, new_client):
    monkeypatch.setenv("MAMIA_ADMIN_EMAIL", "jaime@jtgcloud.test")
    monkeypatch.setenv("MAMIA_ADMIN_PASSWORD", "temporal-123")
    from app.core import config
    config.reload_settings()
    admin = new_client()
    admin.post("/api/login", json={"email": "jaime@jtgcloud.test", "password": "temporal-123"})
    fam = new_client()
    me = signup(fam, email="ana@x.test", name="Ana")
    assert fam.get("/api/admin/families").status_code == 403
    r = admin.put("/api/admin/codes", json={"codes": [{"code": "AMIGAS", "duration": "6m", "max": 10, "public": False},
                                                       {"code": "LANZAMIENTO", "duration": "1y", "max": 50, "public": True, "aliases": ["LAUNCH"]}]})
    assert r.status_code == 200 and [c["code"] for c in r.json()["codes"]] == ["AMIGAS", "LANZAMIENTO"]
    assert admin.put("/api/admin/codes", json={"codes": [{"code": "A"}, {"code": "a"}]}).status_code == 400
    fid = me["user"]["familyId"]
    assert admin.put(f"/api/admin/families/{fid}/grant", json={"until": "life"}).json()["access"]["kind"] == "gift"
    fams = admin.get("/api/admin/families").json()["families"]
    assert {f["name"] for f in fams} == {"Mi familia", "Familia García"}
    assert admin.delete(f"/api/admin/families/{fid}").status_code == 200
    assert fam.get("/api/me").status_code == 401
