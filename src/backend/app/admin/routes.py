"""Server administration: the families and their access, free time given by hand, backups and the state of the
server (promotions and Stripe are in app.billing.web)."""
from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.accounts.users import User
from app.billing import codes, stripe
from app.billing.status import cancel_for, summary
from app.core import backup, db, mailer, version
from app.core.deps import admin_user
from app.families import service as families
from app.notices import emails

router = APIRouter()


@router.get("/api/admin/overview")
def overview(u: User = Depends(admin_user)):
    with db.ro() as con:
        n_fam = con.execute("SELECT count(*) FROM families").fetchone()[0]
        n_users = con.execute("SELECT count(*) FROM users").fetchone()[0]
        n_push = con.execute("SELECT count(*) FROM push_subs").fetchone()[0]
    return {"families": n_fam, "accounts": n_users, "pushDevices": n_push, "mail": mailer.configured(),
            "stripe": stripe.configured(), "version": version.current(), "backups": backup.listing()[:10],
            "promos": codes.promos()}


@router.get("/api/admin/families")
def list_families(u: User = Depends(admin_user)):
    out = []
    with db.ro() as con:
        for f in con.execute("SELECT * FROM families ORDER BY id DESC"):
            owner = con.execute("SELECT email, name FROM users WHERE id=?", (f["owner_id"],)).fetchone() if f["owner_id"] else None
            stats = con.execute("SELECT count(*), max(last_seen) FROM users WHERE family_id=?", (f["id"],)).fetchone()
            members = con.execute("SELECT count(*) FROM docs WHERE family_id=? AND collection='members' AND data IS NOT NULL",
                                  (f["id"],)).fetchone()[0]
            items = con.execute("SELECT count(*) FROM docs WHERE family_id=? AND data IS NOT NULL", (f["id"],)).fetchone()[0]
            out.append({"id": f["id"], "name": f["name"], "created": f["created_at"],
                        "owner": dict(owner) if owner else None, "accounts": stats[0], "lastSeen": stats[1],
                        "members": members, "items": items, "access": summary(con, f["id"]),
                        "mine": f["id"] == u.family_id})
    return {"families": out}


class GrantIn(BaseModel):
    until: str   # "life", "none" (take the free access away) or YYYY-MM-DD


@router.put("/api/admin/families/{family_id}/grant")
def set_grant(family_id: int, body: GrantIn, u: User = Depends(admin_user)):
    with db.tx() as con:
        if not families.get_family(con, family_id):
            raise HTTPException(404, "Esa familia no existe.")
        if body.until == "none":
            con.execute("DELETE FROM grants WHERE family_id=?", (family_id,))
        elif body.until == "life":
            codes.grant(con, family_id, "admin", None)
        else:
            try:
                day = datetime.strptime(body.until, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(400, "Esa fecha no es válida.")
            codes.grant(con, family_id, "admin", codes.until_ms(day.isoformat()))
        return {"access": summary(con, family_id)}


@router.delete("/api/admin/families/{family_id}")
def delete_family(family_id: int, u: User = Depends(admin_user)):
    if family_id == u.family_id:
        raise HTTPException(400, "Tu propia familia se borra desde Cuenta.")
    with db.tx() as con:
        f = families.get_family(con, family_id)
        if not f:
            raise HTTPException(404, "Esa familia no existe.")
        if con.execute("SELECT 1 FROM users WHERE family_id=? AND is_admin=1", (family_id,)).fetchone():
            raise HTTPException(400, "Esa familia tiene una cuenta de administración del servidor.")
        to = [r["email"] for r in con.execute("SELECT email FROM users WHERE family_id=?", (family_id,))]
        cancel_for(con, family_id)
        families.delete_family(con, family_id)
    emails.family_deleted_by_admin(to, f["name"])
    return {"ok": True}


@router.post("/api/admin/backup")
async def backup_now(u: User = Depends(admin_user)):
    p = await asyncio.to_thread(backup.make)
    return {"ok": True, "name": p.name, "backups": backup.listing()[:10]}
