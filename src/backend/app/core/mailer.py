"""Outgoing email by SMTP: sign-up codes, invitations, password resets, reminders, the daily summary and the notices of
the account, the family and the subscription. As in BodyLens, it is set with environment variables (SMTP_HOST,
SMTP_PORT, SMTP_SECURITY = ssl | starttls | none, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM, SMTP_FROM_NAME) and what is
saved in Administración → Correo wins over them. The password is kept encrypted and never shown.

SMTP_HOST=log does not send anything: every email goes to the server's log (and to SENT), for local development and
the tests."""
from __future__ import annotations

import html
import logging
import os
import re
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from urllib.parse import urlsplit

log = logging.getLogger("mamia.mail")
TIMEOUT = 60
SUBJECT_PREFIX = "Mam-IA · "
LOG_HOST = "log"
SENT: list[dict] = []          # the emails of SMTP_HOST=log (the last 200)

# the fields of the configuration: environment variable (default) → what is saved in Administración wins
FIELDS = {"host": "SMTP_HOST", "port": "SMTP_PORT", "security": "SMTP_SECURITY", "username": "SMTP_USERNAME",
          "password": "SMTP_PASSWORD", "from_address": "SMTP_FROM", "from_name": "SMTP_FROM_NAME"}


def _stored() -> dict:
    from app.core import crypto, db
    stored = dict(db.get_setting("mail", {}) or {})
    if stored.get("password"):
        stored["password"] = crypto.decrypt(stored["password"]) or ""
    return stored


def settings() -> dict:
    stored = _stored()
    E = {k: stored[k] if stored.get(k) not in (None, "") else os.environ.get(var, "") for k, var in FIELDS.items()}
    security = str(E.get("security") or "ssl").strip().lower()
    if security not in ("ssl", "starttls", "none"):
        security = "ssl"
    default_port = {"ssl": 465, "starttls": 587, "none": 25}[security]
    try:
        port = int(E.get("port") or default_port)
    except (TypeError, ValueError):
        port = default_port
    s = {
        "host": str(E.get("host") or "").strip(),
        "port": port,
        "security": security,
        "username": str(E.get("username") or "").strip(),
        "password": str(E.get("password") or ""),
        "from_address": str(E.get("from_address") or E.get("username") or "").strip(),
        "from_name": str(E.get("from_name") or "Mam-IA").strip(),
    }
    s["configured"] = bool(s["host"] and s["from_address"])
    return s


def configured() -> bool:
    return settings()["configured"]


def public_settings() -> dict:
    """The configuration for Administración (without the password)."""
    s = settings()
    out = {k: s[k] for k in ("configured", "host", "port", "security", "username", "from_address", "from_name")}
    out["hasPassword"] = bool(s["password"])
    out["logOnly"] = s["host"] == LOG_HOST
    return out


def page(title: str, paragraphs: list[str], link: tuple[str, str] | None = None, foot: str = "") -> str:
    """Simple HTML email in the app's colours. The paragraphs (and `foot`) come already escaped."""
    button = ""
    if link:
        button = (f'<p style="margin:22px 0 4px"><a href="{html.escape(link[1], quote=True)}" style="background:#C93E66;'
                  f'color:#fff;text-decoration:none;padding:12px 20px;border-radius:12px;font-weight:700;display:inline-block">'
                  f'{html.escape(link[0])}</a></p>')
    body = "".join(f'<p style="margin:0 0 12px">{p}</p>' for p in paragraphs)
    foot = foot or "Mam-IA · la agenda de toda la familia"
    return (f'<!doctype html><html lang="es"><body style="margin:0;background:#F6F3F6;padding:24px 12px;'
            f'font:15px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;color:#231B29">'
            f'<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #E3DCE6;border-radius:18px;padding:24px">'
            f'<div style="font-weight:800;font-size:19px;color:#C93E66;margin-bottom:14px">Mam-IA</div>'
            f'<h1 style="font-size:20px;margin:0 0 12px">{html.escape(title)}</h1>{body}{button}'
            f'<p style="margin:22px 0 0;font-size:12px;color:#5F5568">{foot}</p></div></body></html>')


def _text_of(html_body: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</h1>|</div>|</li>", "\n", html_body)
    t = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>([^<]*)</a>', r"\2: \1", t)
    t = re.sub(r"<li[^>]*>", "· ", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(re.sub(r"\n{3,}", "\n\n", t)).strip()


def _recipients(to: str | list[str]) -> list[str]:
    to = [to] if isinstance(to, str) else to
    return list(dict.fromkeys(x.strip() for x in to if x and x.strip()))


def _helo_name(s: dict) -> str:
    """Public name to greet the mail server with, instead of the container's private address (spam filters distrust
    a HELO like [172.x.x.x]): the host of PUBLIC_URL, else the domain of the sender."""
    from app.core import config
    host = urlsplit(config.settings.public_url).hostname if config.settings.public_url else None
    return host or s["from_address"].split("@")[-1] or "localhost"


def build(s: dict, to: list[str], subject: str, html_body: str, unsubscribe: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = SUBJECT_PREFIX + subject
    msg["From"] = formataddr((s["from_name"], s["from_address"]))
    msg["To"] = ", ".join(to)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=s["from_address"].split("@")[-1] or None)
    if unsubscribe:   # the "unsubscribe" button of the email apps (one click, RFC 8058)
        msg["List-Unsubscribe"] = f"<{unsubscribe}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(_text_of(html_body))
    msg.add_alternative(html_body, subtype="html")
    return msg


def _deliver(s: dict, msg: EmailMessage) -> None:
    if s["host"] == LOG_HOST:
        SENT.append({"to": msg["To"], "subject": msg["Subject"], "text": msg.get_body(("plain",)).get_content(),
                     "unsubscribe": msg["List-Unsubscribe"]})
        del SENT[:-200]
        log.warning("email (SMTP_HOST=log, not sent) to %s: %s\n%s", msg["To"], msg["Subject"], SENT[-1]["text"])
        return
    ctx = ssl.create_default_context()
    helo = _helo_name(s)
    try:
        server = smtplib.SMTP_SSL(s["host"], s["port"], local_hostname=helo, timeout=TIMEOUT, context=ctx) \
            if s["security"] == "ssl" else smtplib.SMTP(s["host"], s["port"], local_hostname=helo, timeout=TIMEOUT)
        with server:
            server.ehlo()
            if s["security"] == "starttls":
                server.starttls(context=ctx)
                server.ehlo()
            if s["username"]:
                server.login(s["username"], s["password"])
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise RuntimeError("El servidor de correo no acepta el usuario o la contraseña (SMTP_USERNAME / SMTP_PASSWORD).") from e
    except (smtplib.SMTPException, OSError) as e:
        raise RuntimeError(f"No se pudo enviar el correo: {type(e).__name__}.") from e


def _by_lang(to: list[str], lang: str | None) -> dict[str, list[str]]:
    """The recipients grouped by language: the one given, else each account's (looked up by address), else Spanish."""
    from app.core import db, i18n
    if i18n.clean(lang):
        return {i18n.clean(lang): to}
    try:
        with db.ro() as con:
            found = {r["e"]: r["lang"] for r in con.execute(
                f"SELECT lower(email) AS e, lang FROM users WHERE lower(email) IN ({','.join('?' * len(to))})",
                [t.lower() for t in to])}
    except Exception:   # noqa: BLE001 — an email always goes, in Spanish if need be
        found = {}
    out: dict[str, list[str]] = {}
    for t in to:
        out.setdefault(i18n.clean(found.get(t.lower())) or i18n.DEFAULT, []).append(t)
    return out


def send(to: str | list[str], subject: str, html_body: str, unsubscribe: str | None = None,
         lang: str | None = None) -> None:
    """Send one email (to one or more addresses, each sees them all), in the language of each recipient (or `lang`).
    Raises RuntimeError with a message in Spanish."""
    from app.core import i18n
    s = settings()
    rcpt = _recipients(to)
    if not s["configured"]:
        raise RuntimeError("El correo saliente no está configurado en este servidor.")
    if not rcpt:
        raise RuntimeError("El correo no tiene destinatarios.")
    for code, group in _by_lang(rcpt, lang).items():
        _deliver(s, build(s, group, i18n.tr(code, subject), i18n.tr_html(code, html_body), unsubscribe))


def send_later(to: str | list[str], subject: str, html_body: str, unsubscribe: str | None = None,
               lang: str | None = None) -> bool:
    """Send in the background (the request does not wait for the SMTP server); failures go to the log.
    False when mail is not configured or there is nobody to send it to."""
    s = settings()
    if not s["configured"] or not _recipients(to):
        log.info("email not sent (mail not configured or no address): %s", subject)
        return False

    def run():
        try:
            send(to, subject, html_body, unsubscribe, lang)
            log.info("email sent: %s", subject)
        except Exception as e:   # noqa: BLE001 — logged, never shown with its details
            log.warning("email not sent: %s — %s", subject, e)

    if s["host"] == LOG_HOST:
        run()           # nothing slow to wait for: at once (the tests read SENT right after)
    else:
        threading.Thread(target=run, name="mamia-mail", daemon=True).start()
    return True
