"""Stripe: the family's subscription paid on the website (card, Google Pay, Apple Pay) with a 7-day free trial.

The family and its first account are made only when Stripe confirms the subscription: the sign-up form is kept as a
pending sign-up (the password encrypted) while the person pays on Stripe's checkout page; the family is created when
they come back, or when Stripe's webhook says the checkout is complete, whichever comes first. Stripe keeps charging
every month or year; its webhooks keep the state of each subscription here. Card details never reach Mam-IA.
Adapted from BodyLens."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import requests

from app.core import crypto, db

API = "https://api.stripe.com/v1"
PLANS = {"monthly": ("month", 250, "mamia_monthly_250"), "yearly": ("year", 2500, "mamia_yearly_2500")}   # cents, EUR
TRIAL_DAYS = 7
ACTIVE = {"active", "trialing", "past_due"}   # past_due: Stripe is still retrying the payment


class StripeError(Exception):
    pass


def settings() -> dict:
    s = db.get_setting("stripe", {}) or {}
    return {"secret": crypto.decrypt(s.get("secret")) if s.get("secret") else None,
            "webhook": crypto.decrypt(s.get("webhook")) if s.get("webhook") else None,
            "prices": s.get("prices") or {}}


def configured() -> bool:
    s = settings()
    return bool(s["secret"] and s["prices"].get("monthly") and s["prices"].get("yearly"))


def _flat(d: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's form encoding: a[b][0][c]=v."""
    out = []
    for k, v in d.items():
        key = f"{prefix}[{k}]" if prefix else str(k)
        if isinstance(v, dict):
            out += _flat(v, key)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                out += _flat(x, f"{key}[{i}]") if isinstance(x, dict) else [(f"{key}[{i}]", str(x))]
        elif v is not None:
            out.append((key, "true" if v is True else "false" if v is False else str(v)))
    return out


def call(method: str, path: str, params: dict | None = None, secret: str | None = None) -> dict:
    key = secret or settings()["secret"]
    if not key:
        raise StripeError("Los pagos con tarjeta no están configurados en este servidor.")
    try:
        r = requests.request(method, API + path, auth=(key, ""), timeout=30,
                             **({"params": _flat(params or {})} if method == "GET" else {"data": _flat(params or {})}))
    except requests.RequestException:
        raise StripeError("Stripe no responde. Inténtalo más tarde.")
    j = r.json() if r.content else {}
    if r.status_code >= 400:
        raise StripeError((j.get("error") or {}).get("message") or f"Stripe: error {r.status_code}")
    return j


def ensure_prices(secret: str) -> dict:
    """The monthly and yearly prices (made in Stripe the first time, found by their lookup key afterwards)."""
    found = call("GET", "/prices", {"lookup_keys": [p[2] for p in PLANS.values()], "active": True}, secret).get("data", [])
    by_key = {p.get("lookup_key"): p["id"] for p in found}
    if all(p[2] in by_key for p in PLANS.values()):
        return {plan: by_key[p[2]] for plan, p in PLANS.items()}
    prod = call("POST", "/products", {"name": "Mam-IA (familia)"}, secret)["id"]
    out = {}
    for plan, (interval, cents, key) in PLANS.items():
        out[plan] = by_key.get(key) or call("POST", "/prices", {
            "product": prod, "currency": "eur", "unit_amount": cents, "lookup_key": key,
            "recurring": {"interval": interval}, "tax_behavior": "inclusive"}, secret)["id"]
    return out


def checkout(plan: str, pending_id: str, email: str, base: str) -> str:
    """URL of Stripe's checkout page for a new subscription with the free trial."""
    s = settings()
    price = s["prices"].get(plan)
    if not price:
        raise StripeError("Ese plan no existe.")
    sess = call("POST", "/checkout/sessions", {
        "mode": "subscription", "line_items": [{"price": price, "quantity": 1}],
        "subscription_data": {"trial_period_days": TRIAL_DAYS, "metadata": {"pending": pending_id}},
        "payment_method_collection": "always", "customer_email": email, "client_reference_id": pending_id,
        "metadata": {"pending": pending_id}, "locale": "es",
        "success_url": f"{base}/bienvenida?session_id={{CHECKOUT_SESSION_ID}}", "cancel_url": f"{base}/#precios",
    })
    return sess["url"]


def portal(customer: str, base: str) -> str:
    return call("POST", "/billing_portal/sessions", {"customer": customer, "return_url": f"{base}/cuenta"})["url"]


def verify_webhook(payload: bytes, header: str, tolerance: int = 600) -> dict:
    """The event, if the Stripe-Signature header is right for the webhook secret."""
    secret = settings()["webhook"]
    if not secret:
        raise StripeError("Webhook sin configurar.")
    parts = dict(p.split("=", 1) for p in (header or "").split(",") if "=" in p)
    t, sigs = parts.get("t", ""), [v for k, v in (p.split("=", 1) for p in (header or "").split(",") if "=" in p) if k == "v1"]
    expected = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    if not t.isdigit() or abs(time.time() - int(t)) > tolerance or not any(hmac.compare_digest(expected, s) for s in sigs):
        raise StripeError("Firma del webhook incorrecta.")
    return json.loads(payload)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
