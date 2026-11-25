"""Google Play: checks a subscription purchase with the Google Play Developer API (subscriptionsv2) and acknowledges
it. The server signs in to Google with a service account of the Play Console (Administration → Google Play), whose key
is stored encrypted. Nothing about the payment itself reaches Mam-IA: only the purchase token and its state.
Ported from BodyLens; in Mam-IA the subscription is the family's (app.billing.play_routes)."""
from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime, timezone

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core import crypto, db

API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
DEFAULT_PACKAGE = "app.mamia.android"
DEFAULT_PRODUCT = "mamia"             # the subscription; its base plans are "monthly" and "yearly"
ACTIVE = {"SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"}


class PlayError(Exception):
    pass


def settings() -> dict:
    s = db.get_setting("play", {}) or {}
    return {"package": s.get("package") or DEFAULT_PACKAGE, "product": s.get("product") or DEFAULT_PRODUCT,
            "sa": crypto.decrypt(s.get("sa")) if s.get("sa") else None}


def configured() -> bool:
    sa = settings()["sa"]
    return bool(sa and sa.get("client_email") and sa.get("private_key"))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


_tokens: dict = {}   # scope → {for, token, exp}


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _access_token(scope: str = SCOPE) -> str:
    """OAuth access token of the service account for a scope (signed JWT, kept until shortly before it expires). The
    business dashboard also uses it to read the reports of Play Console in Cloud Storage."""
    sa = settings()["sa"]
    if not sa:
        raise PlayError("Google Play no está configurado en este servidor.")
    _access = _tokens.setdefault(scope, {})
    if _access.get("for") == sa["client_email"] and _access.get("exp", 0) > time.time() + 60:
        return _access["token"]
    now = int(time.time())
    uri = sa.get("token_uri") or "https://oauth2.googleapis.com/token"
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64(json.dumps({"iss": sa["client_email"], "scope": scope, "aud": uri, "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = _b64(key.sign(f"{head}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256()))
    r = requests.post(uri, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                 "assertion": f"{head}.{claims}.{sig}"}, timeout=20)
    if r.status_code != 200:
        raise PlayError("Google no acepta la cuenta de servicio de Google Play.")
    j = r.json()
    _access.update({"for": sa["client_email"], "token": j["access_token"], "exp": now + int(j.get("expires_in", 3600))})
    return j["access_token"]


def fetch(token: str) -> dict:
    """The subscription purchase as Google sees it (subscriptionsv2.get)."""
    s = settings()
    r = requests.get(f"{API}/{s['package']}/purchases/subscriptionsv2/tokens/{token}",
                     headers={"Authorization": f"Bearer {_access_token()}"}, timeout=20)
    if r.status_code == 404 or r.status_code == 400:
        raise PlayError("Google Play no reconoce esa compra.")
    if r.status_code != 200:
        raise PlayError(f"Google Play no responde ({r.status_code}). Inténtalo más tarde.")
    return r.json()


def acknowledge(token: str, product: str) -> None:
    s = settings()
    try:
        requests.post(f"{API}/{s['package']}/purchases/subscriptions/{product}/tokens/{token}:acknowledge",
                      headers={"Authorization": f"Bearer {_access_token()}"}, json={}, timeout=20)
    except requests.RequestException:
        pass   # Google refunds a purchase not acknowledged in 3 days; the next check acknowledges it again


def cancel(token: str, product: str) -> None:
    """Stops the renewals of a subscription (when its account is deleted)."""
    s = settings()
    requests.post(f"{API}/{s['package']}/purchases/subscriptions/{product}/tokens/{token}:cancel",
                  headers={"Authorization": f"Bearer {_access_token()}"}, json={}, timeout=20)


def _ms(iso: str | None) -> int:
    if not iso:
        return 0
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp() * 1000)
    except ValueError:
        return 0


def check(token: str) -> dict:
    """{active, state, product, basePlan, expiry (ms), acknowledged} of a purchase token."""
    p = fetch(token)
    item = max(p.get("lineItems") or [{}], key=lambda li: _ms(li.get("expiryTime")))
    state = p.get("subscriptionState", "")
    expiry = _ms(item.get("expiryTime"))
    active = state in ACTIVE or (state == "SUBSCRIPTION_STATE_CANCELED" and expiry > time.time() * 1000)
    return {"active": active, "state": state, "product": item.get("productId") or settings()["product"],
            "basePlan": (item.get("offerDetails") or {}).get("basePlanId"), "expiry": expiry,
            "acknowledged": p.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"}
