"""The family's documents: what the server accepts, revisions, deletions and the limits."""
import pytest

from app.data import schema


def _push(client, *changes):
    r = client.post("/api/sync", json={"changes": list(changes)})
    assert r.status_code == 200, r.text
    return r.json()["results"]


def test_valid_and_invalid_documents(client, family):
    res = _push(client,
                {"c": "events", "id": "e1", "data": {"title": " Dentista  Lucas ", "start": "2026-11-26T17:30", "remind": 60,
                                                     "repeat": {"freq": "weekly", "days": [3, 0, 3]}, "hacker": "<script>"}},
                {"c": "events", "id": "e2", "data": {"title": "Sin fecha"}},
                {"c": "events", "id": "e3", "data": {"title": "Fecha mala", "start": "2026-13-01"}},
                {"c": "nope", "id": "x", "data": {}},
                {"c": "tasks", "id": "../etc", "data": {"title": "x"}})
    assert res[0]["ok"] and res[0]["data"] == {"title": "Dentista Lucas", "start": "2026-11-26T17:30", "remind": 60,
                                               "repeat": {"freq": "weekly", "every": 1, "days": [0, 3]}}
    assert [r["ok"] for r in res[1:]] == [False, False, False, False]


def test_revisions_and_deletions(client, family):
    r0 = client.get("/api/sync?since=0").json()["rev"]
    _push(client, {"c": "tasks", "id": "t1", "data": {"title": "Basura"}})
    ch = client.get(f"/api/sync?since={r0}").json()
    assert [d["id"] for d in ch["docs"]] == ["t1"] and ch["rev"] > r0
    _push(client, {"c": "tasks", "id": "t1", "data": None})
    ch2 = client.get(f"/api/sync?since={ch['rev']}").json()
    assert ch2["docs"][0]["data"] is None                               # the tombstone reaches the other devices
    assert all(d["id"] != "t1" for d in client.get("/api/sync?since=0").json()["docs"])   # not in a first download


def test_member_with_account_is_protected(client, family):
    mid = family["user"]["memberId"]
    res = _push(client, {"c": "members", "id": mid, "data": {"name": "Lau", "color": "c3", "userId": 999}},
                {"c": "members", "id": mid, "data": None})
    assert res[0]["ok"] and res[0]["data"]["userId"] == family["user"]["id"] and res[0]["data"]["name"] == "Lau"
    assert not res[1]["ok"]
    # a new member cannot claim an account
    res = _push(client, {"c": "members", "id": "m2", "data": {"name": "Inés", "kind": "kid", "userId": family["user"]["id"]}})
    assert "userId" not in res[0]["data"]


def test_member_limit(client, family):
    res = _push(client, *[{"c": "members", "id": f"k{i}", "data": {"name": f"Peque {i}", "kind": "kid"}} for i in range(8)])
    assert sum(r["ok"] for r in res) == schema.MAX_MEMBERS - 1


def test_too_many_changes_at_once(client, family):
    r = client.post("/api/sync", json={"changes": [{"c": "tasks", "id": f"t{i}", "data": {"title": "x"}} for i in range(501)]})
    assert r.status_code == 400


@pytest.mark.parametrize("c,data,ok", [
    ("tasks", {"title": "Lavadora", "due": "2026-11-24", "time": "25:00"}, False),
    ("tasks", {"title": "Lavadora", "repeat": {"freq": "weekly", "every": 2, "days": [0, 2, 4]}, "rotate": ["a", "b"]}, True),
    ("items", {"text": "Leche"}, False),
    ("items", {"list": "super", "text": "Leche", "qty": "2", "done": True, "src": "menu"}, True),
    ("meals", {"date": "2026-11-23", "slot": "cena", "dish": "Tortilla", "ingredients": ["huevos", "patatas"]}, True),
    ("meals", {"date": "2026-11-23", "slot": "merienda"}, False),
    ("members", {"name": "Inés", "kind": "kid", "info": {"allergies": "Frutos secos", "shoes": "32"}}, True),
    ("members", {"name": "Inés", "info": {"bad key": "x"}}, False),
    ("prefs", {"value": {"sections": ["Fruta"]}}, True),
    ("done", {"title": "Basura", "date": "2026-11-23", "by": "m1"}, True),
])
def test_collections(client, family, c, data, ok):
    assert _push(client, {"c": c, "id": "x1", "data": data})[0]["ok"] is ok
