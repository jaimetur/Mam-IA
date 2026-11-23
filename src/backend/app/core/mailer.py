"""Outgoing email by SMTP (invitations to a family and password resets). Set with environment variables, as in
BodyLens: SMTP_HOST, SMTP_PORT, SMTP_SECURITY (ssl | starttls | none), SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM and
SMTP_FROM_NAME. The password is never stored in the database nor shown."""
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

log = logging.getLogger("mamia.mail")
TIMEOUT = 60


def settings() -> dict:
    security = (os.environ.get("SMTP_SECURITY") or "ssl").strip().lower()
    if security not in ("ssl", "starttls", "none"):
        security = "ssl"
    default_port = {"ssl": 465, "starttls": 587, "none": 25}[security]
    try:
        port = int(os.environ.get("SMTP_PORT") or default_port)
    except ValueError:
        port = default_port
    s = {
        "host": (os.environ.get("SMTP_HOST") or "").strip(),
        "port": port,
        "security": security,
        "username": (os.environ.get("SMTP_USERNAME") or "").strip(),
        "password": os.environ.get("SMTP_PASSWORD") or "",
        "from_address": (os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USERNAME") or "").strip(),
        "from_name": (os.environ.get("SMTP_FROM_NAME") or "Mam-IA").strip(),
    }
    s["configured"] = bool(s["host"] and s["from_address"])
    return s


def configured() -> bool:
    return settings()["configured"]


def page(title: str, paragraphs: list[str], link: tuple[str, str] | None = None) -> str:
    """Simple HTML email in the app's colours. The paragraphs come already escaped."""
    button = ""
    if link:
        button = (f'<p style="margin:22px 0 4px"><a href="{html.escape(link[1], quote=True)}" style="background:#C93E66;'
                  f'color:#fff;text-decoration:none;padding:12px 20px;border-radius:12px;font-weight:700;display:inline-block">'
                  f'{html.escape(link[0])}</a></p>')
    body = "".join(f'<p style="margin:0 0 12px">{p}</p>' for p in paragraphs)
    return (f'<!doctype html><html lang="es"><body style="margin:0;background:#F6F3F6;padding:24px 12px;'
            f'font:15px/1.55 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;color:#231B29">'
            f'<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #E3DCE6;border-radius:18px;padding:24px">'
            f'<div style="font-weight:800;font-size:19px;color:#C93E66;margin-bottom:14px">Mam-IA</div>'
            f'<h1 style="font-size:20px;margin:0 0 12px">{html.escape(title)}</h1>{body}{button}'
            f'<p style="margin:22px 0 0;font-size:12px;color:#5F5568">Mam-IA · la agenda de toda la familia</p></div></body></html>')


def _text_of(html_body: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</h1>|</div>", "\n", html_body)
    t = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>([^<]*)</a>', r"\2: \1", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(re.sub(r"\n{3,}", "\n\n", t)).strip()


def send(to: str, subject: str, html_body: str) -> None:
    """Send one email (raises on failure)."""
    s = settings()
    if not s["configured"]:
        raise RuntimeError("El correo saliente no está configurado en este servidor.")
    msg = EmailMessage()
    msg["Subject"] = f"Mam-IA · {subject}"
    msg["From"] = formataddr((s["from_name"], s["from_address"]))
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=s["from_address"].split("@")[-1] or None)
    msg.set_content(_text_of(html_body))
    msg.add_alternative(html_body, subtype="html")
    ctx = ssl.create_default_context()
    if s["security"] == "ssl":
        server = smtplib.SMTP_SSL(s["host"], s["port"], timeout=TIMEOUT, context=ctx)
    else:
        server = smtplib.SMTP(s["host"], s["port"], timeout=TIMEOUT)
    with server:
        if s["security"] == "starttls":
            server.starttls(context=ctx)
        if s["username"]:
            server.login(s["username"], s["password"])
        server.send_message(msg)


def send_later(to: str, subject: str, html_body: str) -> bool:
    """Send in the background (the request does not wait for the SMTP server). False when mail is not configured."""
    if not configured():
        return False

    def run():
        try:
            send(to, subject, html_body)
        except Exception:   # noqa: BLE001 — logged, never shown with its details
            log.exception("could not send «%s»", subject)

    threading.Thread(target=run, daemon=True).start()
    return True
