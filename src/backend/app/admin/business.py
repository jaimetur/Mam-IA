"""Administración → Negocio: the dashboard of the business (families, subscriptions, income, downloads, Google Play
and the health of the server) for a period, and the tests of each connection.

Every figure says where it comes from and when it was read. Nothing is made up: a source that is not configured says
so, and one that fails says its error without breaking the others. Stripe and Google are asked from the server, with
a cache (STRIPE_TTL, GOOGLE_TTL); the database is read every time.

Sources:
  - the database: families, accounts, subscriptions (stripe_subs, play_subs), free access (grants), read-only families
    (lapses), promotion codes and the downloads of /android.apk (downloads);
  - Stripe: charges and refunds of the period, and the subscriptions (trial conversion and cancellations);
  - Google Play (the service account of Administración → Google Play): the release of each track (edits.tracks) and,
    from the bucket of Play Console reports in Cloud Storage, the installs (stats/installs, daily rows in monthly
    files) and the earnings (earnings/earnings_YYYYMM*.zip, monthly, usually by the 5th of the next month)."""
from __future__ import annotations

import csv
import io
import shutil
import time
import zipfile
from datetime import date, datetime, timedelta, timezone

import requests

from app.billing import codes, play, stripe
from app.core import backup, config, db, mailer

PERIODS = {"7d": 7, "30d": 30, "12m": 365, "all": None}
STRIPE_TTL = 10 * 60
GOOGLE_TTL = 30 * 60
ERROR_TTL = 60
PRICE = {plan: cents for plan, (_, cents, _) in stripe.PLANS.items()}   # list prices, in cents
GCS = "https://storage.googleapis.com/storage/v1/b"
GCS_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"
PAID = {"active", "past_due"}

_cache: dict = {}


# ---------- small helpers ----------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def since(period: str, now: datetime | None = None) -> datetime | None:
    days = PERIODS[period]
    return None if days is None else (now or now_utc()) - timedelta(days=days)


def monthly(period: str) -> bool:
    """The charts of 12 months and since the beginning go by month; the others by day."""
    return PERIODS[period] is None or PERIODS[period] > 31


def buckets(period: str, start: datetime | None, first: str | None, now: datetime | None = None) -> list[str]:
    """The labels of the chart: every day (YYYY-MM-DD) or month (YYYY-MM) of the period, oldest first."""
    now = now or now_utc()
    if monthly(period):
        begin = (start.date() if start else date.fromisoformat((first or iso(now))[:10])).replace(day=1)
        out, d = [], begin
        while d <= now.date():
            out.append(d.isoformat()[:7])
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        return out
    days = PERIODS[period]
    return [(now.date() - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def series(labels: list[str], values: dict[str, float]) -> list[dict]:
    return [{"label": k, "value": values.get(k, 0)} for k in labels]


def cached(key: str, ttl: int, fn, refresh: bool = False) -> dict:
    """fn() kept for ttl seconds (an error, for ERROR_TTL): {data | error, updated}."""
    hit = _cache.get(key)
    if hit and not refresh and time.time() - hit["at"] < hit["ttl"]:
        return hit["value"]
    try:
        value = {"data": fn(), "updated": iso(now_utc())}
        keep = ttl
    except Exception as e:   # noqa: BLE001 — one source failing never breaks the dashboard
        value = {"error": str(e) or e.__class__.__name__, "updated": iso(now_utc())}
        keep = ERROR_TTL
    _cache[key] = {"at": time.time(), "ttl": keep, "value": value}
    return value


def clear_cache() -> None:
    _cache.clear()


def hint(secret: str | None) -> str | None:
    """«…4f2a»: enough to recognise a key without showing it."""
    return f"…{secret[-4:]}" if secret and len(secret) >= 8 else ("…" if secret else None)


# ---------- the database ----------

def users(con, period: str, now: datetime) -> dict:
    start = since(period, now)
    s = iso(start) if start else ""
    first = con.execute("SELECT min(created_at) FROM families").fetchone()[0]
    count = lambda sql, *a: con.execute(sql, a).fetchone()[0]   # noqa: E731
    active = lambda days: count("SELECT count(DISTINCT family_id) FROM users WHERE last_seen >= ?",   # noqa: E731
                                iso(now - timedelta(days=days)))
    cut = 7 if monthly(period) else 10
    per = dict(con.execute(f"SELECT substr(created_at, 1, {cut}), count(*) FROM families WHERE created_at >= ? GROUP BY 1", (s,)))
    return {"families": count("SELECT count(*) FROM families"),
            "newFamilies": count("SELECT count(*) FROM families WHERE created_at >= ?", s),
            "accounts": count("SELECT count(*) FROM users"),
            "newAccounts": count("SELECT count(*) FROM users WHERE created_at >= ?", s),
            "active7": active(7), "active30": active(30),
            "chart": series(buckets(period, start, first, now), per)}


def subscriptions(con, period: str, now: datetime) -> dict:
    now_ms = int(now.timestamp() * 1000)
    web = {"paid": 0, "trial": 0, "cancelAtEnd": 0, "ended": 0, "monthly": 0, "yearly": 0}
    for r in con.execute("SELECT status, plan, cancel_end FROM stripe_subs"):
        if r["status"] in PAID:
            web["paid"] += 1
        elif r["status"] == "trialing":
            web["trial"] += 1
        else:
            web["ended"] += 1
        if r["status"] in stripe.ACTIVE:
            web["cancelAtEnd"] += int(bool(r["cancel_end"]))
        if r["status"] in PAID and r["plan"] in ("monthly", "yearly"):   # by plan: the paying ones
            web[r["plan"]] += 1
    gp = {"paid": 0, "trial": None, "cancelAtEnd": 0, "ended": 0, "monthly": 0, "yearly": 0}
    for r in con.execute("SELECT state, base_plan, expiry_ms FROM play_subs"):
        if r["expiry_ms"] > now_ms:
            gp["paid"] += 1
            gp["cancelAtEnd"] += int(r["state"] == "SUBSCRIPTION_STATE_CANCELED")
            if r["base_plan"] in ("monthly", "yearly"):
                gp[r["base_plan"]] += 1
        else:
            gp["ended"] += 1
    free, by_code = 0, {}
    for g in con.execute("SELECT code, until_ms FROM grants"):
        if codes.active(g):
            free += 1
            by_code[g["code"] or "admin"] = by_code.get(g["code"] or "admin", 0) + 1
    promos = [{"code": c["code"], "used": c.get("used", 0), "max": c.get("max"), "public": bool(c.get("public")),
               "left": None if c.get("max") is None else max(0, c["max"] - c.get("used", 0)), "expires": c.get("expires") or ""}
              for c in codes.codes()]
    return {"web": web, "play": gp, "free": free, "freeByCode": by_code, "promos": promos,
            "readOnly": con.execute("SELECT count(*) FROM lapses").fetchone()[0]}


def mrr(subs: dict) -> dict:
    """Monthly recurring revenue at list prices, in cents: paying subscriptions (not the ones in their free trial);
    the yearly ones count ÷12. Google Play's is before Google's fee."""
    def of(c):
        return round(c["monthly"] * PRICE["monthly"] + c["yearly"] * PRICE["yearly"] / 12)
    web, gp = of(subs["web"]), of(subs["play"])
    return {"web": web, "play": gp, "total": web + gp}


def downloads(con, period: str, now: datetime) -> dict:
    start = since(period, now)
    s = start.date().isoformat() if start else ""
    cut = 7 if monthly(period) else 10
    per = dict(con.execute(f"SELECT substr(day, 1, {cut}), sum(n) FROM downloads WHERE kind='apk' AND day >= ? GROUP BY 1", (s,)))
    first = con.execute("SELECT min(day) FROM downloads WHERE kind='apk'").fetchone()[0]
    return {"period": con.execute("SELECT coalesce(sum(n), 0) FROM downloads WHERE kind='apk' AND day >= ?", (s,)).fetchone()[0],
            "total": con.execute("SELECT coalesce(sum(n), 0) FROM downloads WHERE kind='apk'").fetchone()[0],
            "countingSince": first, "chart": series(buckets(period, start, first, now), per)}


def play_churn(con, period: str, now: datetime) -> dict:
    start = since(period, now)
    lo = int(start.timestamp() * 1000) if start else 0
    hi = int(now.timestamp() * 1000)
    return {"new": con.execute("SELECT count(*) FROM play_subs WHERE created_at >= ?", (iso(start) if start else "",)).fetchone()[0],
            "ended": con.execute("SELECT count(*) FROM play_subs WHERE expiry_ms > ? AND expiry_ms <= ?", (lo, hi)).fetchone()[0]}


def health() -> dict:
    b = backup.listing()
    try:
        du = shutil.disk_usage(config.settings.data_dir)
        disk = {"free": du.free, "total": du.total}
    except OSError:
        disk = None
    m = mailer.settings()
    return {"lastBackup": b[0]["name"] if b else None, "backups": len(b), "disk": disk,
            "mail": {"configured": bool(m["configured"]), "logOnly": m.get("host") == "log"}}


# ---------- Stripe ----------

def _stripe_list(path: str, params: dict, pages: int = 20) -> list[dict]:
    out, after = [], None
    for _ in range(pages):
        j = stripe.call("GET", path, {**params, "limit": 100, **({"starting_after": after} if after else {})})
        out += j.get("data", [])
        if not j.get("has_more") or not out:
            break
        after = out[-1]["id"]
    return out


def stripe_money(period: str, now: datetime) -> dict:
    """Charged and refunded in the period, by month, read from Stripe (cents, EUR)."""
    start = since(period, now)
    created = {"created": {"gte": int(start.timestamp())}} if start else {}
    charges = [c for c in _stripe_list("/charges", created) if c.get("paid") and c.get("status") == "succeeded"]
    refunds = [r for r in _stripe_list("/refunds", created) if r.get("status") in ("succeeded", "pending")]
    by_month: dict[str, int] = {}
    for c in charges:
        k = datetime.fromtimestamp(c["created"], timezone.utc).date().isoformat()[:7]
        by_month[k] = by_month.get(k, 0) + c["amount"]
    for r in refunds:
        k = datetime.fromtimestamp(r["created"], timezone.utc).date().isoformat()[:7]
        by_month[k] = by_month.get(k, 0) - r["amount"]
    return {"charged": sum(c["amount"] for c in charges), "refunded": sum(r["amount"] for r in refunds),
            "charges": len(charges), "refunds": len(refunds), "byMonth": by_month,
            "currency": (charges[0].get("currency") if charges else "eur")}


def trial_funnel(subs: list[dict], start: datetime | None, now: datetime) -> dict:
    """Of the subscriptions whose free trial ended in the period, how many went on paying; and the cancellations of
    the period (the subscription ended, or its owner cancelled it)."""
    lo = int(start.timestamp()) if start else 0
    hi = int(now.timestamp())
    ended_trials = [s for s in subs if s.get("trial_end") and lo <= s["trial_end"] <= hi]
    def paid_after_trial(s):
        gone = s.get("ended_at") or s.get("canceled_at")
        return s.get("status") not in ("incomplete_expired",) and not (gone and gone <= s["trial_end"] + 3600)
    converted = sum(1 for s in ended_trials if paid_after_trial(s))
    cancelled = sum(1 for s in subs if (s.get("canceled_at") or 0) and lo <= s["canceled_at"] <= hi)
    return {"trialsEnded": len(ended_trials), "converted": converted,
            "rate": round(converted / len(ended_trials), 3) if ended_trials else None, "cancelled": cancelled}


def stripe_subs_all() -> list[dict]:
    return _stripe_list("/subscriptions", {"status": "all"})


# ---------- Google Play ----------

def reports_bucket() -> str:
    b = ((db.get_setting("play", {}) or {}).get("reportsBucket") or "").strip()
    return b.removeprefix("gs://").strip("/").split("/")[0]


def gcs_list(bucket: str, prefix: str) -> list[dict]:
    token = play._access_token(GCS_SCOPE)
    out, page = [], None
    for _ in range(20):
        r = requests.get(f"{GCS}/{bucket}/o", params={"prefix": prefix, **({"pageToken": page} if page else {})},
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if r.status_code >= 400:
            raise play.PlayError(_google_error(r))
        j = r.json()
        out += j.get("items", [])
        page = j.get("nextPageToken")
        if not page:
            break
    return out


def gcs_get(bucket: str, name: str) -> bytes:
    from urllib.parse import quote
    r = requests.get(f"{GCS}/{bucket}/o/{quote(name, safe='')}", params={"alt": "media"},
                     headers={"Authorization": f"Bearer {play._access_token(GCS_SCOPE)}"}, timeout=60)
    if r.status_code >= 400:
        raise play.PlayError(_google_error(r))
    return r.content


def _google_error(r) -> str:
    try:
        msg = r.json().get("error", {}).get("message", "")
    except ValueError:
        msg = ""
    if r.status_code in (401, 403):
        return f"Google no deja leerlo ({r.status_code}): la cuenta de servicio necesita permiso. {msg}".strip()
    if r.status_code == 404:
        return "Google no encuentra ese bucket o fichero (404). Revisa el URI de Cloud Storage."
    return f"Google: error {r.status_code}. {msg}".strip()


def read_csv(raw: bytes) -> list[dict]:
    """The CSV files of Play Console come in UTF-16 (the earnings, in UTF-8): both are read."""
    for enc in ("utf-16", "utf-8-sig"):
        try:
            text = raw.decode(enc)
        except UnicodeError:
            continue
        if "," in text[:500]:
            return list(csv.DictReader(io.StringIO(text)))
    return []


def _num(v) -> float:
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else 0.0
    except ValueError:
        return 0.0


def _months(start: datetime | None, now: datetime, first: str = "2020-01") -> list[str]:
    d = (start.date() if start else date.fromisoformat(first + "-01")).replace(day=1)
    out = []
    while d <= now.date():
        out.append(d.strftime("%Y%m"))
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def installs(bucket: str, package: str, period: str, now: datetime) -> dict:
    """Installs of the period from the statistics reports (stats/installs: monthly files with a row per day)."""
    start = since(period, now)
    files = gcs_list(bucket, f"stats/installs/installs_{package}_")
    wanted = set(_months(start, now))
    by_month: dict[str, dict] = {}
    for f in files:
        name = f["name"].rsplit("/", 1)[-1]
        parts = name[:-4].split("_") if name.endswith(".csv") else []
        month = next((p for p in parts if len(p) == 6 and p.isdigit()), None)
        dim = parts[-1] if parts else ""
        if month in wanted and (dim == "overview" or (dim == "country" and by_month.get(month, {}).get("dim") != "overview")):
            by_month[month] = {"dim": dim, "name": f["name"]}
    total, last_day, current, chart = 0.0, None, None, {}
    cut = 7 if monthly(period) else 10
    lo = start.date().isoformat() if start else ""
    for month in sorted(by_month):
        rows = read_csv(gcs_get(bucket, by_month[month]["name"]))
        day_current: dict[str, float] = {}
        for row in rows:
            day = (row.get("Date") or "")[:10]
            if not day or day < lo:
                continue
            n = _num(row.get("Daily User Installs") or row.get("Daily Device Installs"))
            total += n
            chart[day[:cut]] = chart.get(day[:cut], 0) + n
            act = row.get("Installs on active devices") or row.get("Active Device Installs") or row.get("Current Device Installs")
            if act not in (None, ""):
                day_current[day] = day_current.get(day, 0) + _num(act)
        if day_current:
            last_day = max(day_current)
            current = day_current[last_day]
    return {"installs": int(total), "activeDevices": None if current is None else int(current), "lastDay": last_day,
            "months": sorted(by_month), "chart": chart}


def earnings(bucket: str, package: str, period: str, now: datetime) -> dict:
    """What Google Play paid for the app, by month, from the earnings reports (earnings/earnings_YYYYMM*.zip): the
    sales, Google's fee, the taxes and the refunds, in the merchant currency."""
    start = since(period, now)
    wanted = set(_months(start, now))
    months: dict[str, dict] = {}
    for f in gcs_list(bucket, "earnings/earnings_"):
        month = f["name"].rsplit("/", 1)[-1][len("earnings_"):][:6]
        if month not in wanted or not f["name"].endswith(".zip"):
            continue
        with zipfile.ZipFile(io.BytesIO(gcs_get(bucket, f["name"]))) as z:
            for inner in z.namelist():
                for row in read_csv(z.read(inner)):
                    if (row.get("Package ID") or package) != package:
                        continue
                    m = months.setdefault(month, {"sales": 0.0, "fees": 0.0, "taxes": 0.0, "refunds": 0.0, "net": 0.0,
                                                  "currency": row.get("Merchant Currency") or ""})
                    amount = _num(row.get("Amount (Merchant Currency)"))
                    kind = (row.get("Transaction Type") or "").lower()
                    m["net"] += amount
                    if kind in ("charge", "charge rebill"):
                        m["sales"] += amount
                    elif kind.startswith("google fee"):
                        m["fees"] += amount
                    elif kind.startswith("tax"):
                        m["taxes"] += amount
                    elif kind == "charge refund":
                        m["refunds"] += amount
    rounded = {k: {**v, **{f: round(v[f], 2) for f in ("sales", "fees", "taxes", "refunds", "net")}} for k, v in months.items()}
    latest = max(rounded) if rounded else None
    return {"months": rounded, "latest": latest,
            "net": round(sum(v["net"] for v in rounded.values()), 2),
            "currency": next((v["currency"] for v in rounded.values() if v["currency"]), "")}


def tracks(package: str) -> list[dict]:
    """The release of each track in Play Console (a read-only edit, deleted afterwards)."""
    h = {"Authorization": f"Bearer {play._access_token()}"}
    base = f"{play.API}/{package}/edits"
    r = requests.post(base, headers=h, json={}, timeout=30)
    if r.status_code >= 400:
        raise play.PlayError(_google_error(r))
    edit = r.json()["id"]
    try:
        r = requests.get(f"{base}/{edit}/tracks", headers=h, timeout=30)
        if r.status_code >= 400:
            raise play.PlayError(_google_error(r))
        out = []
        for t in r.json().get("tracks", []):
            rel = [{"name": x.get("name"), "status": x.get("status"), "versionCodes": x.get("versionCodes", []),
                    "userFraction": x.get("userFraction")} for x in t.get("releases", [])]
            out.append({"track": t.get("track"), "releases": rel})
        return out
    finally:
        requests.delete(f"{base}/{edit}", headers=h, timeout=30)


# ---------- the dashboard ----------

def dashboard(period: str = "30d", refresh: bool = False) -> dict:
    if period not in PERIODS:
        period = "30d"
    now = now_utc()
    db_src = {"source": "db", "updated": iso(now)}
    with db.ro() as con:
        u = users(con, period, now)
        s = subscriptions(con, period, now)
        dl = downloads(con, period, now)
        pc = play_churn(con, period, now)
    out = {"period": period, "generated": iso(now),
           "users": {**db_src, **u},
           "subscriptions": {**db_src, **s},
           "mrr": {**db_src, **mrr(s)},
           "apk": {**db_src, **dl},
           "playSubs": {**db_src, **pc},
           "health": {"source": "server", "updated": iso(now), **health()}}

    # Stripe: the money of the period and the trials
    if stripe.configured():
        start = since(period, now)
        money = cached(f"stripe:money:{period}", STRIPE_TTL, lambda: stripe_money(period, now), refresh)
        funnel = cached("stripe:subs", STRIPE_TTL, stripe_subs_all, refresh)
        if "data" in funnel:
            funnel = {"data": trial_funnel(funnel["data"], start, now), "updated": funnel["updated"]}
        if "data" in money:   # by month, every month of the period (the first one with money, since the beginning)
            first = min(money["data"]["byMonth"], default=None)
            labels = [f"{m[:4]}-{m[4:]}" for m in _months(start, now, first or now.date().isoformat()[:7])]
            money["data"]["chart"] = series(labels, money["data"]["byMonth"])
        out["stripe"] = {"source": "stripe", "configured": True, "live": bool((stripe.settings()["secret"] or "").startswith(("sk_live", "rk_live"))),
                         "money": money, "funnel": funnel}
    else:
        out["stripe"] = {"source": "stripe", "configured": False}

    # Google Play: tracks, installs and earnings
    ps = play.settings()
    if play.configured():
        pkg = ps["package"]
        out["playTracks"] = {"source": "play", "configured": True,
                             **cached(f"play:tracks:{pkg}", GOOGLE_TTL, lambda: tracks(pkg), refresh)}
        bucket = reports_bucket()
        if bucket:
            out["playInstalls"] = {"source": "play-reports", "configured": True,
                                   **cached(f"play:installs:{bucket}:{pkg}:{period}", GOOGLE_TTL,
                                            lambda: installs(bucket, pkg, period, now), refresh)}
            out["playEarnings"] = {"source": "play-reports", "configured": True,
                                   **cached(f"play:earnings:{bucket}:{pkg}:{period}", GOOGLE_TTL,
                                            lambda: earnings(bucket, pkg, period, now), refresh)}
        else:
            out["playInstalls"] = out["playEarnings"] = {"source": "play-reports", "configured": False, "missing": "bucket"}
    else:
        out["playTracks"] = {"source": "play", "configured": False}
        out["playInstalls"] = out["playEarnings"] = {"source": "play-reports", "configured": False, "missing": "account"}
    return out


# ---------- «Probar conexión» ----------

def test_stripe() -> str:
    if not stripe.settings()["secret"]:
        raise stripe.StripeError("Stripe no está configurado.")
    b = stripe.call("GET", "/balance")
    return "Stripe responde (modo real)." if b.get("livemode") else "Stripe responde (modo de prueba)."


def test_play() -> str:
    if not play.configured():
        raise play.PlayError("Falta la clave de la cuenta de servicio.")
    t = tracks(play.settings()["package"])
    return f"Google Play responde: {len(t)} canales en Play Console."


def test_reports() -> str:
    bucket = reports_bucket()
    if not bucket:
        raise play.PlayError("Falta el URI de Cloud Storage de los informes.")
    if not play.configured():
        raise play.PlayError("Falta la clave de la cuenta de servicio.")
    n = len(gcs_list(bucket, "stats/installs/")) + len(gcs_list(bucket, "earnings/"))
    return f"Cloud Storage responde: {n} informes de instalaciones e ingresos."
