"""Invitations to the family, people with and without an account, roles, handing it over and deleting it."""
from conftest import confirm, mails_to, signup


def _invite(client, **body):
    r = client.post("/api/family/invites", json=body)
    assert r.status_code == 200, r.text
    return r.json()["link"].split("c=")[1]


def _join(c, code, name="Pablo", email="pablo@familia.test", password="secreto-pablo"):
    """Accept an invitation shared by hand: the address is confirmed with the emailed code."""
    r = c.post("/api/invites/accept", json={"code": code, "name": name, "email": email, "password": password})
    assert r.status_code == 200 and r.json()["email"] == email, r.text
    return confirm(c, r.json(), email)


def test_invite_link_and_accept(client, family, new_client):
    code = _invite(client)   # no email: shared by hand
    pablo = new_client()
    prev = pablo.get(f"/api/invites/{code}").json()
    assert prev["family"] == "Familia García" and prev["by"] == "Laura"
    r = pablo.post("/api/invites/accept", json={"code": code, "name": "Pablo", "email": "pablo@familia.test", "password": "secreto-pablo"})
    assert r.status_code == 200 and "verify" in r.json()            # shared by hand: the address is confirmed first
    assert pablo.get("/api/me").status_code == 401
    assert pablo.post("/api/web/verify", json={"id": r.json()["verify"], "code": "000000"}).status_code == 400
    assert confirm(pablo, r.json(), "pablo@familia.test")["signedIn"]
    me = pablo.get("/api/me").json()
    assert me["user"]["familyId"] == family["user"]["familyId"] and me["user"]["role"] == "member"
    # welcome to Pablo, and a notice to Laura (who administers the family)
    assert any("Ya estás en Familia García" in m["subject"] for m in mails_to("pablo@familia.test"))
    assert any("Pablo se ha unido" in m["subject"] for m in mails_to("laura@familia.test"))
    # the invitation is used up
    assert pablo.get(f"/api/invites/{code}").status_code == 404
    # both see the same data at once
    pablo.post("/api/sync", json={"changes": [{"c": "items", "id": "i1", "data": {"list": "super", "text": "Leche"}}]})
    texts = [d["data"]["text"] for d in client.get("/api/sync?since=0").json()["docs"] if d["c"] == "items"]
    assert texts == ["Leche"]


def test_invite_linked_to_an_existing_profile(client, family, new_client):
    client.post("/api/sync", json={"changes": [{"c": "members", "id": "mPablo", "data": {"name": "Pablo", "kind": "adult", "color": "c2"}}]})
    code = _invite(client, email="pablo@familia.test", memberId="mPablo")
    pablo = new_client()
    r = pablo.post("/api/invites/accept", json={"code": code, "name": "Pablo Pérez", "email": "otro@familia.test", "password": "secreto-pablo"})
    assert r.status_code == 400 and "pablo@familia.test" in r.json()["detail"]
    r = pablo.post("/api/invites/accept", json={"code": code, "name": "Pablo Pérez", "email": "pablo@familia.test", "password": "secreto-pablo"})
    assert r.status_code == 200 and r.json() == {"ok": True}        # sent to that address: no code needed
    me = pablo.get("/api/me").json()
    assert me["user"]["memberId"] == "mPablo"
    m = [d for d in client.get("/api/sync?since=0").json()["docs"] if d["id"] == "mPablo"][0]
    assert m["data"]["userId"] == me["user"]["id"] and m["data"]["color"] == "c2"


def test_only_family_admins_invite_and_manage(client, family, new_client):
    code = _invite(client)
    pablo = new_client()
    _join(pablo, code)
    assert pablo.post("/api/family/invites", json={}).status_code == 403
    pid = pablo.get("/api/me").json()["user"]["id"]
    assert client.put(f"/api/family/accounts/{pid}", json={"role": "admin"}).status_code == 200
    assert pablo.post("/api/family/invites", json={}).status_code == 200
    # nobody can take the owner out
    assert pablo.delete(f"/api/family/accounts/{family['user']['id']}").status_code == 400


def test_remove_account_keeps_the_person(client, family, new_client):
    code = _invite(client)
    pablo = new_client()
    _join(pablo, code)
    me = pablo.get("/api/me").json()["user"]
    client.post("/api/sync", json={"changes": [{"c": "tasks", "id": "t1", "data": {"title": "Basura", "who": me["memberId"]}}]})
    assert client.delete(f"/api/family/accounts/{me['id']}").status_code == 200
    assert pablo.get("/api/me").status_code == 401
    assert any("Ya no estás en Familia García" in m["subject"] for m in mails_to("pablo@familia.test"))
    docs = {(d["c"], d["id"]): d["data"] for d in client.get("/api/sync?since=0").json()["docs"]}
    assert "userId" not in docs[("members", me["memberId"])] and docs[("tasks", "t1")]["who"] == me["memberId"]


def test_owner_must_hand_over_before_leaving(client, family, new_client):
    code = _invite(client)
    pablo = new_client()
    _join(pablo, code)
    r = client.post("/api/me/delete", json={"password": "secreto-largo"})
    assert r.status_code == 400 and "pásala" in r.json()["detail"]
    pid = pablo.get("/api/me").json()["user"]["id"]
    assert client.post("/api/family/transfer", json={"userId": pid}).status_code == 200
    assert any("Ahora gestionas Familia García" in m["subject"] for m in mails_to("pablo@familia.test"))
    assert client.post("/api/me/delete", json={"password": "secreto-largo"}).status_code == 200
    assert any("Tu cuenta se ha borrado" in m["subject"] for m in mails_to("laura@familia.test"))
    fam = pablo.get("/api/family").json()
    assert fam["ownerId"] == pid and len(fam["accounts"]) == 1


def test_delete_family_and_another_familys_data_is_apart(client, family, new_client):
    other = new_client()
    signup(other, email="ana@otra.test", name="Ana", family="Familia Ruiz")
    other.post("/api/sync", json={"changes": [{"c": "tasks", "id": "t1", "data": {"title": "Secreto de Ana"}}]})
    assert not [d for d in client.get("/api/sync?since=0").json()["docs"] if d["c"] == "tasks"]
    assert client.post("/api/family/delete", json={"password": "secreto-largo"}).status_code == 200
    assert other.get("/api/sync?since=0").status_code == 200


def test_export_and_import(client, family, new_client):
    client.post("/api/sync", json={"changes": [{"c": "events", "id": "e1", "data": {"title": "Dentista", "start": "2026-11-26T17:30"}}]})
    copy = client.get("/api/family/export").json()
    assert copy["app"] == "Mam-IA" and any(d["id"] == "e1" for d in copy["docs"])
    assert all("userId" not in d["data"] for d in copy["docs"])
    other = new_client()
    signup(other, email="ana@otra.test", name="Ana")
    r = other.post("/api/family/import", json={"docs": copy["docs"]})
    assert r.status_code == 200 and r.json()["imported"] >= 1
    assert any(d["id"] == "e1" for d in other.get("/api/sync?since=0").json()["docs"])
