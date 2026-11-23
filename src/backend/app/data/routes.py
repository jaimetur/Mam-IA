"""Synchronisation of the family's data: every device downloads the changes after its last revision and sends its own.
The app asks every few seconds while it is open, so what one person ticks off the others see at once."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.accounts.users import User
from app.core import db
from app.core.deps import json_body, signed_in_user, writer
from app.data import store
from app.data.schema import Invalid

router = APIRouter()


@router.get("/api/sync")
def pull(since: int = 0, u: User = Depends(signed_in_user)):
    with db.ro() as con:
        rev = db.current_rev(con)
        docs = store.changes_since(con, u.family_id, max(0, since))
    return {"rev": rev, "full": since <= 0, "docs": docs}


@router.post("/api/sync")
async def push(request: Request, u: User = Depends(writer)):
    body = await json_body(request)
    changes = body.get("changes") if isinstance(body, dict) else None
    try:
        with db.tx() as con:
            results = store.apply(con, u.family_id, u.id, changes or [])
            rev = db.current_rev(con)
    except Invalid as e:
        raise HTTPException(400, str(e))
    return {"rev": rev, "results": results}
