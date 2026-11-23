"""The family's documents: reading the changes since a revision and applying the changes a device sends.

Every write gets the next global revision; a device asks for everything after the last revision it has, so it can
work offline and catch up later. The last write wins. Deleting keeps a tombstone (data NULL) so other devices learn
about it."""
from __future__ import annotations

import json
import secrets
import sqlite3

from app.core import db
from app.data import schema
from app.data.schema import Invalid

MAX_CHANGES = 500


def new_id(prefix: str = "") -> str:
    return prefix + secrets.token_urlsafe(9).replace("-", "x").replace("_", "y")


def _row(r: sqlite3.Row) -> dict:
    return {"c": r["collection"], "id": r["id"], "data": json.loads(r["data"]) if r["data"] is not None else None,
            "rev": r["rev"], "at": r["updated_at"], "by": r["updated_by"]}


def changes_since(con: sqlite3.Connection, family_id: int, since: int) -> list[dict]:
    if since <= 0:   # a first download: only what exists
        rows = con.execute("SELECT * FROM docs WHERE family_id=? AND data IS NOT NULL ORDER BY rev", (family_id,))
    else:
        rows = con.execute("SELECT * FROM docs WHERE family_id=? AND rev>? ORDER BY rev", (family_id, since))
    return [_row(r) for r in rows]


def get(con: sqlite3.Connection, family_id: int, collection: str, doc_id: str) -> dict | None:
    r = con.execute("SELECT data FROM docs WHERE family_id=? AND collection=? AND id=?",
                    (family_id, collection, doc_id)).fetchone()
    return json.loads(r["data"]) if r and r["data"] is not None else None


def all_of(con: sqlite3.Connection, family_id: int, collection: str) -> dict[str, dict]:
    rows = con.execute("SELECT id, data FROM docs WHERE family_id=? AND collection=? AND data IS NOT NULL",
                       (family_id, collection))
    return {r["id"]: json.loads(r["data"]) for r in rows}


def put(con: sqlite3.Connection, family_id: int, collection: str, doc_id: str, data: dict | None,
        user_id: int | None) -> int:
    """Write a document (already checked) or its tombstone; returns its revision."""
    rev = db.next_rev(con)
    con.execute(
        "INSERT INTO docs(family_id, collection, id, data, rev, updated_at, updated_by) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(family_id, collection, id) DO UPDATE SET data=excluded.data, rev=excluded.rev, "
        "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
        (family_id, collection, doc_id, None if data is None else json.dumps(data, ensure_ascii=False, separators=(",", ":")),
         rev, db.now_iso(), user_id))
    return rev


def _apply_one(con: sqlite3.Connection, family_id: int, user_id: int | None, c: str, doc_id: str, data) -> dict | None:
    if c not in schema.SPEC:
        raise Invalid("Esa colección no existe.")
    if not isinstance(doc_id, str) or not schema.ID_RE.match(doc_id):
        raise Invalid("El identificador no es válido.")
    old = get(con, family_id, c, doc_id)
    if data is None:
        if old is None:
            return None
        if c == "members" and old.get("userId"):
            raise Invalid("Esa persona tiene su propia cuenta: quítala de la familia desde Familia.")
        put(con, family_id, c, doc_id, None, user_id)
        return None
    clean = schema.clean(c, data)
    if c == "members":
        if old and old.get("userId"):          # the link to an account is the server's, never a device's
            clean["userId"] = old["userId"]
        elif old is None:
            n = con.execute("SELECT count(*) FROM docs WHERE family_id=? AND collection='members' AND data IS NOT NULL",
                            (family_id,)).fetchone()[0]
            if n >= schema.MAX_MEMBERS:
                raise Invalid(f"Una familia puede tener hasta {schema.MAX_MEMBERS} personas.")
    elif old is None:
        n = con.execute("SELECT count(*) FROM docs WHERE family_id=?", (family_id,)).fetchone()[0]
        if n >= schema.MAX_DOCS_PER_FAMILY:
            raise Invalid("La familia ha llegado al máximo de datos guardados.")
    if clean == old:
        return clean
    put(con, family_id, c, doc_id, clean, user_id)
    return clean


def apply(con: sqlite3.Connection, family_id: int, user_id: int | None, changes: list) -> list[dict]:
    """Apply a device's changes; each one answers on its own (one bad document does not stop the rest)."""
    if not isinstance(changes, list) or len(changes) > MAX_CHANGES:
        raise Invalid(f"Envía como mucho {MAX_CHANGES} cambios a la vez.")
    out = []
    for ch in changes:
        if not isinstance(ch, dict):
            out.append({"ok": False, "error": "Cambio no válido."})
            continue
        c, doc_id = ch.get("c"), ch.get("id")
        try:
            data = _apply_one(con, family_id, user_id, c, doc_id, ch.get("data"))
            out.append({"c": c, "id": doc_id, "ok": True, "data": data})
        except Invalid as e:
            out.append({"c": c, "id": doc_id, "ok": False, "error": str(e),
                        "data": get(con, family_id, c, doc_id) if c in schema.SPEC and isinstance(doc_id, str) else None})
    return out


def seed_family(con: sqlite3.Connection, family_id: int) -> None:
    """What a new family starts with: the shopping list and a few things "of always"."""
    put(con, family_id, "lists", "super", {"name": "Súper", "kind": "compra", "order": 0}, None)
    put(con, family_id, "lists", "farmacia", {"name": "Farmacia", "kind": "compra", "order": 1}, None)
    for text, section in (("Leche", "Lácteos y huevos"), ("Pan", "Panadería"), ("Huevos", "Lácteos y huevos"),
                          ("Fruta", "Fruta y verdura"), ("Papel higiénico", "Higiene")):
        put(con, family_id, "staples", new_id("s"), {"text": text, "section": section, "list": "super"}, None)
