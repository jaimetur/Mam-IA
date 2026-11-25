"""Languages: the dictionaries of lang/, the language of each page, of each account and of its emails."""
import json

import pytest

from conftest import confirm, mails_to


@pytest.fixture()
def langs(server, tmp_path, monkeypatch):
    """A small English dictionary instead of the real ones (they are checked by tools/i18n_check.py)."""
    d = tmp_path / "lang"
    d.mkdir()
    (d / "i18n.js").write_text("/* translator */")
    # English is the base: es.json bridges each English message to the Spanish of the code
    (d / "es.json").write_text(json.dumps({
        "Hi, {0}.": "Hola, {0}.", "Your code is {0}": "Tu código es {0}", "Your code: {0}": "Tu código: {0}",
        "All day": "Todo el día", "{0} drives": "lleva {0}", "Sign in": ["Entrar", "Iniciar sesión"], "Untranslated": "Sin traducir",
    }), encoding="utf-8")
    (d / "fr.json").write_text(json.dumps({"All day": "Toute la journée", "Sign in": "Se connecter"}), encoding="utf-8")
    monkeypatch.setenv("I18N_DIR", str(d))
    from app.core import config
    config.reload_settings()
    return d


def test_translate_texts_patterns_and_html(langs):
    from app.core import i18n
    assert i18n.tr("en", "Todo el día") == "All day"
    assert i18n.tr("en", "  Hola, Laura. ") == " Hi, Laura. "          # spaces are collapsed, as in lang/i18n.js
    assert i18n.tr("en", "17:30 · lleva Pablo") == "17:30 · Pablo drives"
    assert i18n.tr("en", "Algo sin traducir") == "Algo sin traducir"
    assert i18n.tr("es", "Todo el día") == "Todo el día"
    assert i18n.tr("en", "Iniciar sesión") == "Sign in"                # several Spanish texts, one message
    assert i18n.tr("fr", "Todo el día") == "Toute la journée"
    assert i18n.tr("fr", "Sin traducir") == "Untranslated"              # not translated yet: in English
    assert i18n.tr_html("en", '<html lang="es"><p>Todo el día</p></html>') == '<html lang="en"><p>All day</p></html>'


def test_language_of_the_request(langs):
    from app.core import i18n

    class R:
        def __init__(self, cookies=None, accept=""):
            self.cookies, self.headers = cookies or {}, {"accept-language": accept}
    assert i18n.request_lang(R()) == "en"                                   # nothing chosen: English
    assert i18n.request_lang(R(accept="ca-ES,ca;q=0.9,es;q=0.8")) == "en"   # not the browser's language
    assert i18n.request_lang(R({"mamia_lang": "fr"}, "de")) == "fr"         # the one chosen in the picker


def test_pages_load_their_dictionary(client, langs):
    client.cookies.clear()                                  # someone who has not chosen a language: English
    r = client.get("/entrar", headers={"accept-language": "es-ES"})
    assert '<script src="/lang/en.js?v=' in r.text and '<script src="/lang/i18n.js?v=' in r.text
    assert r.text.index("/lang/en.js") < r.text.index("/static/common/pages.js")   # before the page's own scripts
    assert r.headers["content-language"] == "en"
    js = client.get("/lang/en.js").text
    assert 'window.MI_LANG="en"' in js and '"Entrar": "Sign in"' in js
    assert '"MI_I18N={}' not in client.get("/lang/es.js").text and client.get("/lang/xx.js").status_code == 404
    assert client.get("/lang/i18n.js").status_code == 200
    assert "/lang/en.js" in client.get("/").text
    client.cookies.set("mamia_lang", "fr")                  # the one chosen in the picker
    assert "/lang/fr.js" in client.get("/").text


def test_account_language_and_emails(client, langs, outbox):
    client.cookies.set("mamia_lang", "en")
    r = client.post("/api/web/signup", json={"name": "Ann", "email": "ann@x.test", "password": "secreto-largo", "code": "LANZAMIENTO"})
    m = mails_to("ann@x.test")[-1]
    assert m["subject"].startswith("Mam-IA · Your code is ") and "Hi, Ann." in m["text"]
    confirm(client, r.json(), "ann@x.test")
    me = client.get("/api/me").json()["user"]
    assert me["lang"] == "en"                                        # kept from the page she was using
    client.cookies.delete("mamia_lang")
    assert "/lang/en.js" in client.get("/app").text                  # the account's language wins
    assert client.put("/api/me", json={"lang": "klingon"}).status_code == 400
    assert client.put("/api/me", json={"lang": "de"}).json()["user"]["lang"] == "de"
    assert "/lang/de.js" in client.get("/app").text


def test_english_when_the_language_is_not_known(client, outbox):   # the real dictionaries of lang/
    """English for whoever's language is not known: pages (their lang, title and description) and emails; and the
    goodbye emails go in the language of the account, which no longer exists when they leave."""
    client.cookies.clear()
    page = client.get("/").text
    assert '<html lang="en"' in page and "<title>Mam-IA · The whole family's calendar, out of your head</title>" in page
    client.cookies.set("mamia_lang", "es")
    assert '<html lang="es"' in client.get("/").text and "fuera de tu cabeza</title>" in client.get("/").text
    client.cookies.set("mamia_lang", "fr")
    r = client.post("/api/web/signup", json={"name": "Anne", "email": "anne@x.test", "password": "secreto-largo", "code": "LANZAMIENTO"})
    import re
    code = re.search(r"(\d{6})", mails_to("anne@x.test")[-1]["subject"]).group(1)   # «Votre code est …»
    assert client.post("/api/web/verify", json={"id": r.json()["verify"], "code": code}).json()["signedIn"]
    assert client.post("/api/me/delete", json={"password": "secreto-largo"}).status_code == 200
    assert mails_to("anne@x.test")[-1]["subject"].startswith("Mam-IA · Ton compte a été supprimé")   # in French, after the deletion
    from app.core import mailer
    assert mailer._by_lang(["nadie@x.test"], None) == {"en": ["nadie@x.test"]}


def test_accounts_from_before_keep_spanish(client):
    """The accounts made before English became the default (lang NULL) keep Spanish, once."""
    from app.core import db
    with db.tx() as con:
        fid = con.execute("INSERT INTO families(name, created_at) VALUES('F', datetime('now'))").lastrowid
        con.execute("INSERT INTO users(email, name, pw_hash, family_id, created_at) VALUES('old@x.test','Old','x',?,datetime('now'))", (fid,))
        con.execute("DELETE FROM settings WHERE key='langs_backfilled'")
    db.init_db()
    with db.tx() as con:
        assert con.execute("SELECT lang FROM users WHERE email='old@x.test'").fetchone()[0] == "es"
        con.execute("INSERT INTO users(email, name, pw_hash, family_id, created_at) VALUES('new@x.test','New','x',?,datetime('now'))", (fid,))
    db.init_db()
    with db.ro() as con:
        assert con.execute("SELECT lang FROM users WHERE email='new@x.test'").fetchone()[0] is None   # only once


def test_real_translations_are_complete():
    """lang/: every language translates every English message, with the same placeholders, and the catalog is
    up to date with the code (python3 tools/i18n_extract.py)."""
    import sys
    from pathlib import Path
    tools = Path(__file__).resolve().parents[1] / "tools"
    sys.path.insert(0, str(tools))
    import i18n_check
    import i18n_extract
    assert i18n_check.main([]) == 0
    es = json.loads((i18n_extract.LANG / "es.json").read_text(encoding="utf-8"))
    have = i18n_extract.covered(es)
    missing = [t for t in i18n_extract.found() if t not in have and t not in i18n_extract.IGNORE]
    assert not missing, f"texts of the code without an English message (run tools/i18n_extract.py): {missing[:10]}"
