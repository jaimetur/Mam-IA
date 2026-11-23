"""Accounts, sessions and password resets. Every account belongs to one family (see app.families)."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core import config, db
from app.core.security import hash_password, new_token, password_problem, token_hash, verify_password

EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
THEMES = ("auto", "light", "dark")
ACCENTS = ("rosa", "lavanda", "menta", "coral")


class UserError(ValueError):
    """An error with a message for the person using the app."""


def clean_email(email: str | None) -> str:
    email = (email or "").strip()
    if not email:
        raise UserError("Escribe tu correo electrónico.")
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise UserError("El correo electrónico no es válido.")
    return email


def clean_name(name: str | None, what: str = "tu nombre") -> str:
    name = " ".join((name or "").split())
    if not name or len(name) > 60:
        raise UserError(f"Escribe {what} (hasta 60 caracteres).")
    return name


@dataclass
class User:
    id: int
    email: str
    name: str
    family_id: int
    member_id: str | None
    role: str
    is_admin: bool
    must_change: bool
    theme: str
    accent: str
    mail_reminders: bool = True     # reminders of events and tasks by email
    mail_digest: bool = False       # the summary of the day by email, every morning

    @classmethod
    def from_row(cls, r: sqlite3.Row) -> "User":
        return cls(r["id"], r["email"], r["name"], r["family_id"], r["member_id"], r["role"], bool(r["is_admin"]),
                   bool(r["must_change"]), r["theme"], r["accent"], bool(r["mail_reminders"]), bool(r["mail_digest"]))

    @property
    def family_admin(self) -> bool:
        return self.role == "admin"

    def public(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "familyId": self.family_id,
                "memberId": self.member_id, "role": self.role, "isAdmin": self.is_admin,
                "mustChange": self.must_change, "theme": self.theme, "accent": self.accent,
                "mailReminders": self.mail_reminders, "mailDigest": self.mail_digest}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_user(con: sqlite3.Connection, user_id: int) -> User | None:
    r = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return User.from_row(r) if r else None


def get_by_email(con: sqlite3.Connection, email: str) -> User | None:
    r = con.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", ((email or "").strip(),)).fetchone()
    return User.from_row(r) if r else None


def family_users(con: sqlite3.Connection, family_id: int) -> list[User]:
    return [User.from_row(r) for r in con.execute("SELECT * FROM users WHERE family_id=? ORDER BY id", (family_id,))]


def create_user(con: sqlite3.Connection, email: str, name: str, password: str, family_id: int, *,
                role: str = "member", is_admin: bool = False, must_change: bool = False) -> User:
    email = clean_email(email)
    name = clean_name(name)
    if p := password_problem(password):
        raise UserError(p)
    if get_by_email(con, email):
        raise UserError("Ya hay una cuenta con ese correo: entra con ella.")
    cur = con.execute(
        "INSERT INTO users(email, name, pw_hash, family_id, role, is_admin, must_change, created_at) VALUES(?,?,?,?,?,?,?,?)",
        (email, name, hash_password(password), family_id, role, int(is_admin), int(must_change), db.now_iso()))
    return get_user(con, cur.lastrowid)  # type: ignore[return-value]


def authenticate(con: sqlite3.Connection, email: str, password: str) -> User | None:
    r = con.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE", ((email or "").strip(),)).fetchone()
    ok = verify_password(r["pw_hash"] if r else None, password or "")
    return User.from_row(r) if (r and ok) else None


def check_password(con: sqlite3.Connection, user_id: int, password: str) -> bool:
    r = con.execute("SELECT pw_hash FROM users WHERE id=?", (user_id,)).fetchone()
    return verify_password(r["pw_hash"] if r else None, password or "")


def set_password(con: sqlite3.Connection, user_id: int, password: str, keep_session: str | None = None) -> None:
    """New password; every other session of the account is closed."""
    if p := password_problem(password):
        raise UserError(p)
    con.execute("UPDATE users SET pw_hash=?, must_change=0 WHERE id=?", (hash_password(password), user_id))
    con.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user_id, token_hash(keep_session or "")))


def update_profile(con: sqlite3.Connection, user: User, name: str | None = None, theme: str | None = None,
                   accent: str | None = None, email: str | None = None, mail_reminders: bool | None = None,
                   mail_digest: bool | None = None) -> None:
    if name is not None:
        name = clean_name(name)
        con.execute("UPDATE users SET name=? WHERE id=?", (name, user.id))
    if theme is not None:
        if theme not in THEMES:
            raise UserError("Ese tema no está disponible.")
        con.execute("UPDATE users SET theme=? WHERE id=?", (theme, user.id))
    if accent is not None:
        if accent not in ACCENTS:
            raise UserError("Ese color no está disponible.")
        con.execute("UPDATE users SET accent=? WHERE id=?", (accent, user.id))
    if email is not None:
        email = clean_email(email)
        other = get_by_email(con, email)
        if other and other.id != user.id:
            raise UserError("Ya hay otra cuenta con ese correo.")
        con.execute("UPDATE users SET email=? WHERE id=?", (email, user.id))
    if mail_reminders is not None:
        con.execute("UPDATE users SET mail_reminders=? WHERE id=?", (int(mail_reminders), user.id))
    if mail_digest is not None:
        con.execute("UPDATE users SET mail_digest=? WHERE id=?", (int(mail_digest), user.id))


# ---------- sessions ----------

def create_session(con: sqlite3.Connection, user_id: int) -> str:
    token = new_token()
    now = _utcnow()
    con.execute("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES(?,?,?,?)",
                (token_hash(token), user_id, now.isoformat(timespec="seconds"),
                 (now + timedelta(days=config.settings.session_days)).isoformat(timespec="seconds")))
    con.execute("DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(timespec="seconds"),))
    con.execute("UPDATE users SET last_seen=? WHERE id=?", (db.now_iso(), user_id))
    return token


def session_user(con: sqlite3.Connection, token: str | None) -> User | None:
    if not token:
        return None
    r = con.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at > ?",
                    (token_hash(token), _utcnow().isoformat(timespec="seconds"))).fetchone()
    return User.from_row(r) if r else None


def delete_session(con: sqlite3.Connection, token: str | None) -> None:
    if token:
        con.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))


# ---------- password resets ----------

RESET_HOURS = 2


def create_reset(con: sqlite3.Connection, user_id: int) -> str:
    token = new_token(24)
    con.execute("DELETE FROM password_resets WHERE user_id=? OR expires_at < ?", (user_id, db.now_iso()))
    con.execute("INSERT INTO password_resets(token_hash, user_id, expires_at) VALUES(?,?,?)",
                (token_hash(token), user_id, (_utcnow() + timedelta(hours=RESET_HOURS)).isoformat(timespec="seconds")))
    return token


def use_reset(con: sqlite3.Connection, token: str, password: str) -> User:
    r = con.execute("SELECT * FROM password_resets WHERE token_hash=?", (token_hash(token),)).fetchone()
    if not r or r["used_at"] or r["expires_at"] < db.now_iso():
        raise UserError("El enlace para cambiar la contraseña no es válido o ha caducado. Pide otro.")
    set_password(con, r["user_id"], password)
    con.execute("DELETE FROM sessions WHERE user_id=?", (r["user_id"],))
    con.execute("UPDATE password_resets SET used_at=? WHERE token_hash=?", (db.now_iso(), token_hash(token)))
    return get_user(con, r["user_id"])  # type: ignore[return-value]
