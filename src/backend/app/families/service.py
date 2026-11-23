"""Families: creating one with its first account, invitations, removing people, handing it over and deleting it.

A family has accounts (adults who sign in; role "admin" can manage the family, the owner also pays) and members (every
person of the family, with or without an account: kids are members without one). Each account is linked to its
member document ("userId" in the document, "member_id" in the account)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.accounts import users
from app.accounts.users import User, UserError
from app.core import config, db
from app.core.security import new_token, token_hash
from app.data import schema, store

COLOR_ORDER = ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"]


def clean_family_name(name: str | None) -> str:
    name = " ".join((name or "").split())
    if not name:
        return "Mi familia"
    if len(name) > 60:
        raise UserError("El nombre de la familia puede tener hasta 60 caracteres.")
    return name


def get_family(con: sqlite3.Connection, family_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM families WHERE id=?", (family_id,)).fetchone()


def _free_color(con: sqlite3.Connection, family_id: int) -> str:
    used = {m.get("color") for m in store.all_of(con, family_id, "members").values()}
    return next((c for c in COLOR_ORDER if c not in used), "c8")


def _link_member(con: sqlite3.Connection, u: User, member_id: str | None = None) -> str:
    """Link the account to an existing member (e.g. the profile "Pablo" made before inviting him) or to a new one."""
    members = store.all_of(con, u.family_id, "members")
    m = members.get(member_id or "")
    if m is not None and not m.get("userId"):
        data = {**m, "userId": u.id, "kind": "adult"}
        mid = member_id
    else:
        if len(members) >= schema.MAX_MEMBERS:
            raise UserError(f"Una familia puede tener hasta {schema.MAX_MEMBERS} personas.")
        mid = store.new_id("m")
        data = {"name": u.name.split(" ")[0][:40], "kind": "adult", "color": _free_color(con, u.family_id),
                "order": len(members), "userId": u.id}
    store.put(con, u.family_id, "members", mid, data, u.id)
    con.execute("UPDATE users SET member_id=? WHERE id=?", (mid, u.id))
    return mid  # type: ignore[return-value]


def create_family(con: sqlite3.Connection, family_name: str | None, name: str, email: str, password: str, *,
                  is_admin: bool = False, must_change: bool = False) -> User:
    """A new family with its first account (its owner and admin), its member and the starting lists."""
    # checked before anything is written, so a bad email does not leave an empty family behind
    users.clean_email(email)
    users.clean_name(name)
    fam = clean_family_name(family_name)
    cur = con.execute("INSERT INTO families(name, tz, created_at) VALUES(?,?,?)", (fam, config.settings.timezone, db.now_iso()))
    fid = cur.lastrowid
    u = users.create_user(con, email, name, password, fid, role="admin", is_admin=is_admin, must_change=must_change)
    con.execute("UPDATE families SET owner_id=? WHERE id=?", (u.id, fid))
    _link_member(con, u)
    store.seed_family(con, fid)
    return users.get_user(con, u.id)  # type: ignore[return-value]


def info(con: sqlite3.Connection, family_id: int) -> dict:
    f = get_family(con, family_id)
    accounts = [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "memberId": u.member_id,
                 "owner": u.id == f["owner_id"]} for u in users.family_users(con, family_id)]
    now = db.now_iso()
    invites = [{"id": r["id"], "email": r["email"] or "", "memberId": r["member_id"], "expires": r["expires_at"]}
               for r in con.execute("SELECT * FROM family_invites WHERE family_id=? AND used_by IS NULL AND expires_at>? "
                                    "ORDER BY id DESC", (family_id, now))]
    return {"id": f["id"], "name": f["name"], "tz": f["tz"], "ownerId": f["owner_id"], "accounts": accounts,
            "invites": invites, "maxMembers": schema.MAX_MEMBERS}


def rename(con: sqlite3.Connection, family_id: int, name: str) -> None:
    con.execute("UPDATE families SET name=? WHERE id=?", (clean_family_name(name), family_id))


# ---------- invitations ----------

def create_invite(con: sqlite3.Connection, by: User, email: str | None, member_id: str | None) -> str:
    """An invitation link to join the family (sent by email when there is one, or shared by hand)."""
    email = users.clean_email(email) if (email or "").strip() else None
    if email:
        other = users.get_by_email(con, email)
        if other and other.family_id == by.family_id:
            raise UserError("Esa persona ya está en tu familia.")
        if other:
            raise UserError("Ese correo ya tiene una cuenta en otra familia.")
    if member_id:
        m = store.get(con, by.family_id, "members", member_id)
        if m is None:
            raise UserError("Esa persona no está en tu familia.")
        if m.get("userId"):
            raise UserError("Esa persona ya tiene su propia cuenta.")
    elif len(store.all_of(con, by.family_id, "members")) >= schema.MAX_MEMBERS:
        raise UserError(f"Una familia puede tener hasta {schema.MAX_MEMBERS} personas.")
    pending = con.execute("SELECT count(*) FROM family_invites WHERE family_id=? AND used_by IS NULL AND expires_at>?",
                          (by.family_id, db.now_iso())).fetchone()[0]
    if pending >= 20:
        raise UserError("Hay demasiadas invitaciones pendientes: anula alguna antes.")
    code = new_token(18)
    now = datetime.now(timezone.utc)
    con.execute("INSERT INTO family_invites(token_hash, family_id, created_by, email, member_id, created_at, expires_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (token_hash(code), by.family_id, by.id, email, member_id, now.isoformat(timespec="seconds"),
                 (now + timedelta(days=config.settings.invite_days)).isoformat(timespec="seconds")))
    return code


def invite_row(con: sqlite3.Connection, code: str) -> sqlite3.Row:
    r = con.execute("SELECT * FROM family_invites WHERE token_hash=?", (token_hash(code or ""),)).fetchone()
    if not r or r["used_by"] is not None or r["expires_at"] <= db.now_iso():
        raise UserError("La invitación no es válida o ha caducado. Pide otra a quien te invitó.")
    return r


def invite_preview(con: sqlite3.Connection, code: str) -> dict:
    r = invite_row(con, code)
    f = get_family(con, r["family_id"])
    by = users.get_user(con, r["created_by"]) if r["created_by"] else None
    m = store.get(con, r["family_id"], "members", r["member_id"]) if r["member_id"] else None
    return {"family": f["name"], "by": by.name if by else "", "email": r["email"] or "",
            "name": (m or {}).get("name", "")}


def accept_invite(con: sqlite3.Connection, code: str, name: str, email: str, password: str) -> User:
    r = invite_row(con, code)
    if r["email"] and r["email"].lower() != (email or "").strip().lower():
        raise UserError(f"Esta invitación es para {r['email']}: usa ese correo.")
    u = users.create_user(con, email, name, password, r["family_id"], role="member")
    _link_member(con, u, r["member_id"])
    con.execute("UPDATE family_invites SET used_by=?, used_at=? WHERE id=?", (u.id, db.now_iso(), r["id"]))
    return users.get_user(con, u.id)  # type: ignore[return-value]


def cancel_invite(con: sqlite3.Connection, family_id: int, invite_id: int) -> None:
    con.execute("DELETE FROM family_invites WHERE id=? AND family_id=? AND used_by IS NULL", (invite_id, family_id))


# ---------- people and ownership ----------

def _owner_id(con: sqlite3.Connection, family_id: int) -> int | None:
    return get_family(con, family_id)["owner_id"]


def remove_account(con: sqlite3.Connection, by: User, user_id: int) -> None:
    """Take an account out of the family. The person stays as a member without an account (their tasks and events keep
    their name); the account itself is deleted."""
    target = users.get_user(con, user_id)
    if not target or target.family_id != by.family_id:
        raise UserError("Esa cuenta no está en tu familia.")
    if target.id == _owner_id(con, by.family_id):
        raise UserError("No se puede quitar a quien paga la familia. Antes, pasa la familia a otra persona.")
    _unlink_and_delete(con, target)


def _unlink_and_delete(con: sqlite3.Connection, target: User) -> None:
    if target.member_id:
        m = store.get(con, target.family_id, "members", target.member_id)
        if m is not None:
            m.pop("userId", None)
            store.put(con, target.family_id, "members", target.member_id, m, None)
    con.execute("DELETE FROM users WHERE id=?", (target.id,))


def set_role(con: sqlite3.Connection, by: User, user_id: int, role: str) -> None:
    if role not in ("admin", "member"):
        raise UserError("Ese papel no existe.")
    target = users.get_user(con, user_id)
    if not target or target.family_id != by.family_id:
        raise UserError("Esa cuenta no está en tu familia.")
    if target.id == _owner_id(con, by.family_id) and role != "admin":
        raise UserError("Quien paga la familia siempre puede administrarla.")
    con.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))


def transfer(con: sqlite3.Connection, by: User, user_id: int) -> None:
    """Hand the family over to another adult with an account (they will manage the subscription)."""
    if by.id != _owner_id(con, by.family_id):
        raise UserError("Solo quien paga la familia puede pasársela a otra persona.")
    target = users.get_user(con, user_id)
    if not target or target.family_id != by.family_id or target.id == by.id:
        raise UserError("Elige otra persona de tu familia con cuenta.")
    con.execute("UPDATE families SET owner_id=? WHERE id=?", (target.id, by.family_id))
    con.execute("UPDATE users SET role='admin' WHERE id=?", (target.id,))


def leave(con: sqlite3.Connection, u: User) -> None:
    """Delete one's own account. The owner of a family with other accounts has to hand it over first; the owner of a
    family alone in it deletes the whole family (delete_family)."""
    if u.id == _owner_id(con, u.family_id):
        others = [x for x in users.family_users(con, u.family_id) if x.id != u.id]
        if others:
            raise UserError("Eres quien paga la familia: antes de borrar tu cuenta, pásala a otra persona en Familia, "
                            "o borra la familia entera.")
        delete_family(con, u.family_id)
        return
    if u.is_admin:
        n = con.execute("SELECT count(*) FROM users WHERE is_admin=1 AND id<>?", (u.id,)).fetchone()[0]
        if not n:
            raise UserError("Eres la única cuenta de administración del servidor.")
    _unlink_and_delete(con, u)


def delete_family(con: sqlite3.Connection, family_id: int) -> None:
    """Delete the family and everything in it: its accounts, data and subscription records (the caller cancels the
    subscription with the payment provider first)."""
    con.execute("DELETE FROM families WHERE id=?", (family_id,))


# ---------- export and import ----------

def export(con: sqlite3.Connection, family_id: int) -> dict:
    f = get_family(con, family_id)
    docs = [{"c": d["c"], "id": d["id"], "data": {k: v for k, v in d["data"].items() if k != "userId"}}
            for d in store.changes_since(con, family_id, 0)]
    from app.core import version
    return {"app": "Mam-IA", "version": version.release()["version"], "exportedAt": db.now_iso(),
            "family": {"name": f["name"], "tz": f["tz"]}, "docs": docs}


def import_docs(con: sqlite3.Connection, u: User, docs: list) -> dict:
    """Add a copy's documents to the family (existing ones with the same id are replaced; members with an account are
    left as they are)."""
    if not isinstance(docs, list) or len(docs) > 20_000:
        raise UserError("La copia no es válida.")
    ok = bad = 0
    for i in range(0, len(docs), store.MAX_CHANGES):
        part = [d for d in docs[i:i + store.MAX_CHANGES] if isinstance(d, dict)]
        part = [d for d in part if not (d.get("c") == "members" and (store.get(con, u.family_id, "members", d.get("id") or "") or {}).get("userId"))]
        for res in store.apply(con, u.family_id, u.id, part):
            ok, bad = (ok + 1, bad) if res.get("ok") else (ok, bad + 1)
    return {"imported": ok, "skipped": bad}
