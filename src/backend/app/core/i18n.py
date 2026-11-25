"""Languages. English is the base language of the translations: lang/catalog.json lists every message in English,
and each language has lang/<code>.json = {"English message": "translation"} (with patterns like «{0} plans»), so
anybody can translate Mam-IA from English. The code itself is written in Spanish, so lang/es.json = {"English
message": "the Spanish text exactly as in the code"} (or a list of them) bridges the two. In the browser,
lang/i18n.js translates the pages with the dictionary made here; here the same is done for the emails and the push
notifications.

Each account chooses its language (users.lang); without a session, the one chosen in the language picker of the
pages (the cookie mamia_lang). When the language of someone is not known, English (DEFAULT): the pages, the emails and
the notifications. The code itself is written in Spanish (SOURCE), so Spanish needs no dictionary. Adapted from BodyLens's app.core.i18n."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from app.core import config

LANGS = {"es": "Español", "en": "English", "ca": "Català", "fr": "Français", "it": "Italiano", "de": "Deutsch",
         "pt": "Português", "nl": "Nederlands", "zh": "中文", "ja": "日本語"}
SOURCE = "es"    # the language the code is written in (its texts need no translation)
DEFAULT = "en"   # the language of someone whose language is not known (a visitor, an account without one)
COOKIE = "mamia_lang"
EDGE = re.compile(r"^([\s ·—–\-:,;|.]*)(.*?)([\s ·—–\-:,;|]*)$", re.S)
LETTER = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")


def clean(lang: str | None) -> str | None:
    lang = (lang or "").strip().lower()[:5].replace("_", "-").split("-")[0]
    return lang if lang in LANGS else None


def from_header(accept: str | None) -> str | None:
    """The first language of Accept-Language that Mam-IA has («ca-ES,ca;q=0.9,es;q=0.8» → ca)."""
    for part in (accept or "").split(","):
        code = clean(part.split(";")[0])
        if code:
            return code
    return None


def request_lang(request, user=None) -> str:
    """The language of a request: the account's, else the one chosen in the picker (cookie), else English."""
    if user is not None and getattr(user, "lang", None) in LANGS:
        return user.lang
    return clean(request.cookies.get(COOKIE)) or DEFAULT


def _file(lang: str):
    return config.settings.lang_dir / f"{lang}.json"


def stamp(lang: str) -> int:
    """Changes whenever a file the dictionary of ``lang`` is made from changes (cache-busting in URLs)."""
    t = 0
    for p in (_file("es"), _file(lang)):
        try:
            t = max(t, int(p.stat().st_mtime))
        except OSError:
            pass
    return t


def _read(lang: str) -> dict:
    try:
        return json.loads(_file(lang).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=16)
def _compose(lang: str, version: int) -> tuple[dict, list]:
    """Spanish text of the code → English message (es.json) → its translation in ``lang`` (English itself for
    "en"; a message not translated yet is shown in English)."""
    es, tr = _read("es"), ({} if lang == "en" else _read(lang))
    d: dict[str, str] = {}
    for msgid, spanish in es.items():
        target = msgid if lang == "en" else (tr.get(msgid) or msgid)
        if not isinstance(target, str) or not target.strip():
            continue
        for text in (spanish if isinstance(spanish, list) else [spanish]):
            if isinstance(text, str) and text and text != target:
                d.setdefault(text, target)
    pats = []
    for k, v in d.items():
        if "{0}" not in k:
            continue
        nums = re.findall(r"\{(\d)\}", k)
        rx = re.sub(r"\\\{(\d)\\\}", "(.*?)", re.escape(k))
        pats.append((re.compile("^" + rx + "$", re.S), v, nums, len(k)))
    pats.sort(key=lambda p: -p[3])
    return d, pats


def dictionary(lang: str) -> tuple[dict, list]:
    """Spanish text → text in ``lang``, and the patterns of the texts with {0}… (Spanish has none: it is the source)."""
    if lang not in LANGS or lang == SOURCE:
        return {}, []
    return _compose(lang, stamp(lang))


def tr(lang: str, text: str, _depth: int = 0) -> str:
    """Translate one text (with the same trimming as lang/i18n.js); unknown texts stay as they are."""
    if not text or not LETTER.search(text):
        return text
    d, pats = dictionary(lang)
    if not d:
        return text
    pre, core, suf = EDGE.match(re.sub(r"[\s ]+", " ", text)).groups()
    if core in d:
        return pre + d[core] + suf
    for rx, t, nums, _ in pats:
        m = rx.match(core)
        if m:
            def part(x):
                if x.group(1) not in nums:
                    return ""
                val = m.group(nums.index(x.group(1)) + 1)
                return tr(lang, val, _depth + 1) if _depth < 2 else val
            return pre + re.sub(r"\{(\d)\}", part, t) + suf
    if " · " in core and _depth < 3:   # «17:30 · lleva Pablo»: piece by piece
        return pre + " · ".join(tr(lang, p, _depth + 1) for p in core.split(" · ")) + suf
    return text


def tr_html(lang: str, html_text: str) -> str:
    """Translate the texts between the tags of an HTML (the emails)."""
    if lang == SOURCE:
        return html_text
    out = re.sub(r">([^<>]+)<", lambda m: ">" + tr(lang, m.group(1)) + "<", html_text)
    return out.replace('<html lang="es">', f'<html lang="{lang}">')


def head(lang: str) -> str:
    """The scripts every page loads first: its dictionary and the translator (lang/i18n.js)."""
    from app.core import version
    return (f'<script src="/lang/{lang}.js?v={stamp(lang)}"></script>'
            f'<script src="/lang/i18n.js?v={version.stamp()}"></script>')


def script(lang: str) -> str:
    """/lang/<code>.js: the language, the list of languages and the dictionary, for lang/i18n.js."""
    d, _ = dictionary(lang)
    return (f"window.MI_LANG={json.dumps(lang)};window.MI_LANGS={json.dumps(LANGS, ensure_ascii=False)};"
            f"window.MI_I18N={json.dumps(d, ensure_ascii=False)};")
