"""The account of Google Play's reviewers (app.demo.play_review): made once, filled with sample data, refreshed."""


def test_reviewer_account_is_made_filled_and_refreshed(server, client):
    from app.demo import play_review
    r = play_review.fill("playreview@jtgcloud.test", "clave-del-revisor")
    assert r["made"] and r["documents"] > 30
    assert client.post("/api/login", json={"email": "playreview@jtgcloud.test", "password": "clave-del-revisor"}).status_code == 200
    me = client.get("/api/me").json()
    assert me["billing"]["plan"] == "gift" and me["billing"]["expiry"] is None and not me["billing"]["readOnly"]
    names = sorted(a["name"] for a in me["family"]["accounts"])
    assert names == ["Alex", "Sam (demo)"]
    docs = client.get("/api/sync?since=0").json()["docs"]
    kinds = {d["c"] for d in docs if d["data"]}
    assert {"members", "events", "tasks", "items", "meals", "done"} <= kinds
    n = len([d for d in docs if d["data"]])
    # again: nothing duplicated, no new password needed, the demo partner cannot sign in
    r2 = play_review.fill("playreview@jtgcloud.test")
    assert not r2["made"]
    assert len([d for d in client.get("/api/sync?since=0").json()["docs"] if d["data"]]) == n
    assert client.post("/api/login", json={"email": "sam@demo.mamia.invalid", "password": "!demo-account-no-password"}).status_code == 401
    # no email ever goes to a demo account
    from app.core import mailer
    assert mailer.send_later("sam@demo.mamia.invalid", "Prueba", "<p>x</p>") is False


def test_password_file_is_written_and_never_printed(server, tmp_path, capsys):
    from app.demo import play_review
    f = tmp_path / "secrets" / "playreview.txt"
    assert play_review.main(["revisor@jtgcloud.test", "--password-file", str(f)]) == 0
    email, password = f.read_text().split()
    assert email == "revisor@jtgcloud.test" and len(password) >= 12 and password not in capsys.readouterr().out
    assert oct(f.stat().st_mode & 0o777) == "0o600"
    assert play_review.main(["revisor@jtgcloud.test", "--password-file", str(f)]) == 0   # again: refreshed only
    assert f.read_text().split()[1] == password
