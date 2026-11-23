"""Confirming an email address with a 6-digit code before it is used: signing up, joining a family with an invitation
that was not sent to that address, and changing the address of an account.

What is waiting for the code is kept as a pending sign-up (pending_signups, the same table that keeps a sign-up while
the person pays): its data says what it is ("kind") and holds the hash of the code, the attempts and the sendings."""
from __future__ import annotations

import html
import json
import secrets
import sqlite3
import time

from app.accounts.users import UserError
from app.core import crypto, db, mailer
from app.core.security import token_hash

CODE_MINUTES = 30
MAX_TRIES = 5
MAX_SENDS = 5
RESEND_SECONDS = 60
PURPOSE = {"signup": "crear tu cuenta de Mam-IA", "join": "unirte a tu familia en Mam-IA",
           "email": "cambiar el correo de tu cuenta de Mam-IA"}


def _code() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


def _hash(pid: str, code: str) -> str:
    return token_hash(f"{pid}:{code.strip()}")


def _email(to: str, code: str, kind: str, name: str = "", lang: str | None = None) -> None:
    """Send the code (at once: if the email cannot go, the person is told now)."""
    hello = f"Hola, {html.escape(name.split()[0])}." if name.strip() else "Hola."
    mailer.send(to, f"Tu código es {code}", mailer.page(f"Tu código: {code}", [
        hello,
        f"Para {PURPOSE.get(kind, 'seguir')}, escribe este código en la página donde lo has pedido:",
        f'<span style="font-size:28px;font-weight:800;letter-spacing:6px">{code}</span>',
        f"Vale durante {CODE_MINUTES} minutos. Si no lo has pedido tú, no hagas nada: sin el código no se hace nada "
        "con tu correo.",
    ]), lang=lang)


def start(con: sqlite3.Connection, kind: str, email: str, data: dict) -> tuple[str, str]:
    """Keep `data` waiting for the code; returns (id, code). The caller sends the code with send() (after the
    transaction, so a slow mail server does not hold the database)."""
    if not mailer.configured():
        raise UserError("Ahora mismo no podemos enviar correos, y hace falta para confirmar tu dirección. "
                        "Inténtalo más tarde.")
    pid, code = crypto.new_token(18), _code()
    rec = {**data, "kind": kind, "email": email, "check": _hash(pid, code), "tries": 0, "sends": 1, "sent": time.time()}
    con.execute("DELETE FROM pending_signups WHERE created_at < datetime('now','-2 days')")
    con.execute("INSERT INTO pending_signups(id, data, created_at) VALUES(?,?,datetime('now'))", (pid, json.dumps(rec)))
    return pid, code


def send(pid: str, rec: dict, code: str) -> None:
    """Email the code; if it cannot be sent, the pending confirmation is forgotten and a UserError raised."""
    try:
        _email(rec["email"], code, rec["kind"], rec.get("name", ""), rec.get("lang"))
    except RuntimeError as e:
        with db.tx() as con:
            forget(con, pid)
        raise UserError(f"{e} Revisa la dirección o inténtalo más tarde.") from e


def load(con: sqlite3.Connection, pid: str) -> dict:
    r = con.execute("SELECT data FROM pending_signups WHERE id=?", (pid or "",)).fetchone()
    rec = json.loads(r["data"]) if r else None
    if not rec or "check" not in rec:
        raise UserError("Esa confirmación ya no está pendiente: vuelve a empezar.")
    return rec


def _save(con: sqlite3.Connection, pid: str, rec: dict) -> None:
    con.execute("UPDATE pending_signups SET data=? WHERE id=?", (json.dumps(rec), pid))


def check(pid: str, code: str) -> dict:
    """The data waiting for this code when the code is right (it is then marked as confirmed). Wrong codes count, and
    are saved even though an error is raised; after MAX_TRIES, or once it has expired, it has to be started again."""
    error = None
    with db.tx() as con:
        rec = load(con, pid)
        if rec.get("verified"):
            return rec
        if time.time() - rec["sent"] > CODE_MINUTES * 60:
            raise UserError("El código ha caducado: pide otro.")
        if secrets.compare_digest(_hash(pid, "".join((code or "").split())), rec["check"]):
            rec["verified"] = True
            _save(con, pid, rec)
            return rec
        rec["tries"] += 1
        if rec["tries"] >= MAX_TRIES:
            forget(con, pid)
            error = "Has escrito mal el código demasiadas veces: vuelve a empezar."
        else:
            _save(con, pid, rec)
            left = MAX_TRIES - rec["tries"]   # whole sentences, so each one can be translated
            error = ("El código no es correcto. Te queda 1 intento." if left == 1
                     else f"El código no es correcto. Te quedan {left} intentos.")
    raise UserError(error)


def resend(con: sqlite3.Connection, pid: str) -> tuple[dict, str]:
    """A new code for a pending confirmation (not too often)."""
    rec = load(con, pid)
    if rec.get("verified"):
        raise UserError("Tu correo ya está confirmado.")
    wait = RESEND_SECONDS - (time.time() - rec["sent"])
    if wait > 0:
        raise UserError(f"Espera {int(wait) + 1} segundos para pedir otro código.")
    if rec["sends"] >= MAX_SENDS:
        raise UserError("Ya te hemos enviado varios códigos: revisa la carpeta de spam o vuelve a empezar.")
    code = _code()
    rec.update(check=_hash(pid, code), tries=0, sends=rec["sends"] + 1, sent=time.time())
    _save(con, pid, rec)
    return rec, code


def forget(con: sqlite3.Connection, pid: str) -> None:
    con.execute("DELETE FROM pending_signups WHERE id=?", (pid,))


def public(pid: str, rec: dict) -> dict:
    """What the page needs to ask for the code."""
    return {"verify": pid, "email": rec["email"], "minutes": CODE_MINUTES}
