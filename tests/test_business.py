"""Administración → Negocio: the dashboard with made-up data (Stripe and Google are simulated), its sums (MRR, trial
conversion, periods), the downloads of the APK, the reports of Play Console and that no answer carries a secret."""
import csv
import io
import json
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from conftest import signup

SECRET = "sk_test_51SECRETabcdefghijklmnop4f2a"
WEBHOOK = "whsec_SECRETwebhook9876"
SA = {"type": "service_account", "client_email": "play-billing@jtgcloud-play.iam.gserviceaccount.com",
      "private_key_id": "0123456789abcdef7e1d", "token_uri": "https://oauth2.test/token",
      "private_key": "-----BEGIN PRIVATE KEY-----\nSECRETKEYBODY\n-----END PRIVATE KEY-----\n"}
SMTP_PASSWORD = "SECRET-smtp-password"


@pytest.fixture()
def admin(server, monkeypatch, new_client):
    monkeypatch.setenv("MAMIA_ADMIN_EMAIL", "jaime@jtgcloud.test")
    monkeypatch.setenv("MAMIA_ADMIN_PASSWORD", "temporal-123")
    from app.admin import business
    from app.core import config
    config.reload_settings()
    business.clear_cache()
    a = new_client()
    assert a.post("/api/login", json={"email": "jaime@jtgcloud.test", "password": "temporal-123"}).status_code == 200
    return a


def _now_iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def _family(con, name, days_ago):
    cur = con.execute("INSERT INTO families(name, tz, created_at) VALUES(?,?,?)", (name, "Europe/Madrid", _now_iso(days_ago)))
    return cur.lastrowid


def test_only_for_administrators(client, family):
    assert client.get("/api/admin/business").status_code == 403
    assert client.get("/api/admin/keys").status_code == 403
    assert client.post("/api/admin/business/test/stripe").status_code == 403


def test_dashboard_from_the_database(admin, new_client):
    from app.core import db
    signup(new_client(), email="ana@x.test", name="Ana", family="Los Ruiz")   # a new family today (yearly plan asked)
    ms = lambda days: int((time.time() + days * 86400) * 1000)   # noqa: E731
    with db.tx() as con:
        old = _family(con, "Antigua", 100)
        a, b, c, d, e = (_family(con, f"F{i}", 3) for i in range(5))
        sub = "INSERT INTO stripe_subs(family_id, customer_id, subscription_id, plan, status, period_end_ms, updated_at, cancel_end) VALUES(?,?,?,?,?,?,?,?)"
        con.execute(sub, (a, "cus_a", "sub_a", "monthly", "active", ms(20), _now_iso(), 0))
        con.execute(sub, (b, "cus_b", "sub_b", "yearly", "active", ms(200), _now_iso(), 1))
        con.execute(sub, (c, "cus_c", "sub_c", "monthly", "trialing", ms(5), _now_iso(), 0))
        con.execute(sub, (old, "cus_o", "sub_o", "monthly", "canceled", ms(-5), _now_iso(), 0))
        play = "INSERT INTO play_subs(family_id, token_hash, token_enc, product_id, base_plan, state, expiry_ms, created_at) VALUES(?,?,?,?,?,?,?,?)"
        con.execute(play, (d, "h1", "x", "mamia", "yearly", "SUBSCRIPTION_STATE_ACTIVE", ms(300), _now_iso(2)))
        con.execute(play, (e, "h2", "x", "mamia", "monthly", "SUBSCRIPTION_STATE_EXPIRED", ms(-2), _now_iso(40)))
        con.execute("INSERT INTO grants(family_id, code, until_ms, created_at) VALUES(?,?,?,datetime('now'))", (old, "LANZAMIENTO", None))
        con.execute("INSERT INTO lapses(family_id, lapsed_at) VALUES(?,?)", (e, _now_iso(2)))
    for _ in range(3):
        admin.get("/android.apk", follow_redirects=False)

    r = admin.get("/api/admin/business?period=30d")
    assert r.status_code == 200
    d = r.json()
    u = d["users"]
    # the admin's own family, Los Ruiz, the old one and 5 made 3 days ago
    assert u["families"] == 8 and u["newFamilies"] == 7 and u["source"] == "db" and u["updated"]
    assert len(u["chart"]) == 30 and sum(x["value"] for x in u["chart"]) == 7
    assert u["active7"] >= 2          # the admin and Ana have just signed in
    s = d["subscriptions"]
    assert s["web"] == {"paid": 2, "trial": 1, "cancelAtEnd": 1, "ended": 1, "monthly": 1, "yearly": 1}
    assert s["play"]["paid"] == 1 and s["play"]["yearly"] == 1 and s["play"]["ended"] == 1
    assert s["freeByCode"]["LANZAMIENTO"] == 1 and s["free"] == sum(s["freeByCode"].values()) and s["readOnly"] == 1
    # MRR: 2,50 € + 25 €/12 on the web (the trial does not count) and 25 €/12 in Google Play
    assert d["mrr"] == {"source": "db", "updated": d["mrr"]["updated"], "web": 250 + 208, "play": 208, "total": 666}
    assert d["apk"]["period"] == 3 and d["apk"]["total"] == 3 and d["apk"]["chart"][-1]["value"] == 3
    assert d["playSubs"]["new"] == 1 and d["playSubs"]["ended"] == 1
    assert d["stripe"] == {"source": "stripe", "configured": False}
    assert d["playTracks"]["configured"] is False and d["playInstalls"]["missing"] == "account"
    assert d["health"]["mail"]["configured"] and d["health"]["disk"]["free"] > 0

    w = admin.get("/api/admin/business?period=7d").json()
    assert len(w["users"]["chart"]) == 7 and w["users"]["newFamilies"] == 7 and w["playSubs"]["new"] == 1
    y = admin.get("/api/admin/business?period=12m").json()
    assert 12 <= len(y["users"]["chart"]) <= 13 and all(len(x["label"]) == 7 for x in y["users"]["chart"])
    assert y["users"]["newFamilies"] == 8
    a = admin.get("/api/admin/business?period=all").json()
    assert a["users"]["newFamilies"] == 8 and a["playSubs"]["ended"] == 1
    assert admin.get("/api/admin/business?period=nonsense").json()["period"] == "30d"


def test_trial_conversion_and_cancellations():
    from app.admin import business
    now = datetime.now(timezone.utc)
    t = lambda days: int((now - timedelta(days=days)).timestamp())   # noqa: E731
    subs = [
        {"status": "active", "trial_end": t(10)},                                   # paying after the trial
        {"status": "canceled", "trial_end": t(8), "canceled_at": t(9), "ended_at": t(8)},   # gone in the trial
        {"status": "canceled", "trial_end": t(20), "canceled_at": t(5)},            # paid, then cancelled
        {"status": "trialing", "trial_end": t(-3)},                                 # still in its trial
        {"status": "active", "trial_end": t(60)},                                   # trial ended before the period
    ]
    f = business.trial_funnel(subs, now - timedelta(days=30), now)
    assert f == {"trialsEnded": 3, "converted": 2, "rate": 0.667, "cancelled": 2}
    assert business.trial_funnel([], now - timedelta(days=30), now)["rate"] is None


def test_stripe_money(admin, monkeypatch):
    from app.admin import business
    from app.billing import stripe
    from app.core import crypto, db
    with db.tx() as con:
        db.set_setting(con, "stripe", {"secret": crypto.encrypt(SECRET), "webhook": crypto.encrypt(WEBHOOK),
                                       "prices": {"monthly": "price_m", "yearly": "price_y"}})
    now = int(time.time())
    calls = []

    def call(method, path, params=None, secret=None):
        calls.append((path, params))
        if path == "/charges":
            return {"data": [{"id": "ch_1", "amount": 2500, "paid": True, "status": "succeeded", "created": now - 86400, "currency": "eur"},
                             {"id": "ch_2", "amount": 250, "paid": True, "status": "succeeded", "created": now - 3600, "currency": "eur"},
                             {"id": "ch_3", "amount": 250, "paid": False, "status": "failed", "created": now - 3600}], "has_more": False}
        if path == "/refunds":
            return {"data": [{"id": "re_1", "amount": 250, "status": "succeeded", "created": now - 60}], "has_more": False}
        if path == "/subscriptions":
            return {"data": [{"id": "sub_1", "status": "active", "trial_end": now - 5 * 86400}], "has_more": False}
        raise AssertionError(path)
    monkeypatch.setattr(stripe, "call", call)
    d = admin.get("/api/admin/business?period=30d").json()["stripe"]
    assert d["configured"] and d["live"] is False
    m = d["money"]["data"]
    assert m["charged"] == 2750 and m["refunded"] == 250 and m["charges"] == 2 and m["refunds"] == 1
    assert sum(x["value"] for x in m["chart"]) == 2500 and d["money"]["updated"]
    assert d["funnel"]["data"]["converted"] == 1
    assert ("/charges" in [c[0] for c in calls]) and calls[0][1]["created"]["gte"] < now
    n = len(calls)
    admin.get("/api/admin/business?period=30d")
    assert len(calls) == n                       # from the cache
    admin.get("/api/admin/business?period=30d&refresh=1")
    assert len(calls) > n

    def broken(*a, **k):
        raise stripe.StripeError("Stripe no responde. Inténtalo más tarde.")
    monkeypatch.setattr(stripe, "call", broken)
    business.clear_cache()
    d = admin.get("/api/admin/business?period=7d").json()
    assert d["stripe"]["money"]["error"].startswith("Stripe no responde") and d["users"]["families"] >= 1


def _utf16_csv(rows):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return out.getvalue().encode("utf-16")


def test_play_reports_and_tracks(admin, monkeypatch):
    from app.admin import business
    from app.billing import play
    from app.core import crypto, db
    with db.tx() as con:
        db.set_setting(con, "play", {"package": "app.mamia.android", "product": "mamia", "sa": crypto.encrypt(SA),
                                     "reportsBucket": "pubsite_prod_rev_0123"})
    today = datetime.now(timezone.utc).date()
    month = today.strftime("%Y%m")
    days = [today - timedelta(days=i) for i in (40, 3, 1)]
    installs = _utf16_csv([{"Date": d.isoformat(), "Package Name": "app.mamia.android", "Daily User Installs": n,
                            "Installs on active devices": act} for d, n, act in zip(days, (9, 4, 2), (20, 30, 31))])
    earn = io.StringIO()
    w = csv.DictWriter(earn, fieldnames=["Transaction Date", "Transaction Type", "Package ID", "Merchant Currency", "Amount (Merchant Currency)"])
    w.writeheader()
    for kind, amount in (("Charge", "25.00"), ("Google fee", "-3.75"), ("Tax", "-4.34"), ("Charge refund", "-2.50")):
        w.writerow({"Transaction Date": "Nov 3, 2026", "Transaction Type": kind, "Package ID": "app.mamia.android",
                    "Merchant Currency": "EUR", "Amount (Merchant Currency)": amount})
    w.writerow({"Transaction Date": "Nov 3, 2026", "Transaction Type": "Charge", "Package ID": "app.other",
                "Merchant Currency": "EUR", "Amount (Merchant Currency)": "99"})
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as z:
        z.writestr(f"PlayApps_{month}.csv", earn.getvalue())
    months = sorted({d.strftime("%Y%m") for d in days[1:]})   # the months of the recent days: always in the period
    files = {f"stats/installs/installs_app.mamia.android_{m}_overview.csv": installs for m in months}
    files[f"earnings/earnings_{month}_0123-0.zip"] = zbuf.getvalue()
    monkeypatch.setattr(business, "gcs_list", lambda bucket, prefix: [{"name": n} for n in files if n.startswith(prefix)])
    monkeypatch.setattr(business, "gcs_get", lambda bucket, name: files[name])
    monkeypatch.setattr(business, "tracks", lambda pkg: [{"track": "alpha", "releases": [{"name": "0.2.0 (45)", "status": "completed", "versionCodes": ["45"]}]}])

    d = admin.get("/api/admin/business?period=30d").json()
    i = d["playInstalls"]["data"]
    # the same daily rows are in every monthly file of the simulation: only the days of the period count, once per file
    assert i["installs"] == 6 * len(months) and i["activeDevices"] == 31 and i["lastDay"] == days[-1].isoformat()
    e = d["playEarnings"]["data"]
    assert e["months"][month] == {"sales": 25.0, "fees": -3.75, "taxes": -4.34, "refunds": -2.5, "net": 14.41, "currency": "EUR"}
    assert e["latest"] == month and e["currency"] == "EUR"
    assert d["playTracks"]["data"][0]["releases"][0]["name"] == "0.2.0 (45)"

    def denied(pkg):
        raise play.PlayError("Google no deja leerlo (403): la cuenta de servicio necesita permiso.")
    monkeypatch.setattr(business, "tracks", denied)
    business.clear_cache()
    d = admin.get("/api/admin/business?period=7d").json()
    assert "403" in d["playTracks"]["error"] and "data" in d["playInstalls"]


def test_settings_bucket_and_tests(admin, monkeypatch):
    from app.admin import business
    r = admin.put("/api/admin/play", json={"reportsBucket": "gs://pubsite_prod_rev_0123/"})
    assert r.status_code == 200 and r.json()["reportsBucket"] == "pubsite_prod_rev_0123"
    assert admin.put("/api/admin/play", json={"reportsBucket": "gs://otro-bucket"}).status_code == 400
    assert admin.post("/api/admin/business/test/nada").status_code == 404
    r = admin.post("/api/admin/business/test/stripe")
    assert r.status_code == 400 and "Stripe" in r.json()["detail"]
    r = admin.post("/api/admin/business/test/reports")
    assert r.status_code == 400 and "cuenta de servicio" in r.json()["detail"]
    monkeypatch.setattr(business, "test_reports", lambda: "Cloud Storage responde: 3 informes de instalaciones e ingresos.")
    assert admin.post("/api/admin/business/test/reports").json()["message"].startswith("Cloud Storage responde")


def test_no_answer_carries_a_secret(admin, monkeypatch):
    from app.admin import business
    from app.billing import stripe
    from app.core import crypto, db
    with db.tx() as con:
        db.set_setting(con, "stripe", {"secret": crypto.encrypt(SECRET), "webhook": crypto.encrypt(WEBHOOK),
                                       "prices": {"monthly": "price_m", "yearly": "price_y"}})
        db.set_setting(con, "play", {"package": "app.mamia.android", "product": "mamia", "sa": crypto.encrypt(SA)})
        db.set_setting(con, "mail", {"host": "log", "port": 465, "security": "ssl", "username": "u",
                                     "password": crypto.encrypt(SMTP_PASSWORD), "from_address": "mamia@mamia.test"})
    monkeypatch.setattr(stripe, "call", lambda *a, **k: {"data": [], "has_more": False})
    monkeypatch.setattr(business, "tracks", lambda pkg: [])
    texts = [admin.get(p).text for p in ("/api/admin/business?period=all", "/api/admin/keys", "/api/admin/stripe",
                                          "/api/admin/play", "/api/admin/mail", "/api/admin/overview")]
    for t in texts:
        for secret in ("SECRETabcdefghijklmnop", "SECRETwebhook", "SECRETKEYBODY", "PRIVATE KEY", SMTP_PASSWORD):
            assert secret not in t
    keys = {k["id"]: k for k in admin.get("/api/admin/keys").json()["keys"]}
    assert keys["stripe-secret"]["hint"] == "…4f2a" and keys["stripe-webhook"]["hint"] == "…9876"
    assert keys["play-sa"]["hint"] == "…7e1d" and keys["play-sa"]["account"] == SA["client_email"]
    assert keys["smtp"]["set"] and keys["smtp"]["hint"] is None
    st = admin.get("/api/admin/stripe").json()
    assert st["secretHint"] == "…4f2a" and st["plans"]["yearly"]["cents"] == 2500 and st["trialDays"] == 7
    assert json.loads(admin.get("/api/admin/play").text)["keyHint"] == "…7e1d"
