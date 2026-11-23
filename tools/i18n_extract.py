#!/usr/bin/env python3
"""Finds every text the people using Mam-IA can see (the pages, the app, the server's messages and the emails) and
checks that each one has its English message.

English is the base language of the translations: lang/catalog.json lists every message in English, and each
language has lang/<code>.json = {"English message": "translation"}. The code is written in Spanish, so lang/es.json
maps each English message to the Spanish text exactly as it is in the code (a string, or a list when several Spanish
texts share one English message). Variable parts are {0}, {1}… Ported from BodyLens's tools/i18n_extract.py.

Usage: python3 tools/i18n_extract.py
  Writes the Spanish texts of the code that lang/es.json does not have yet to lang/new.json. For each one, add
  {"English message": "texto en español"} to lang/es.json and run this again (it rewrites lang/catalog.json from
  es.json); then add the translations (python3 tools/i18n_check.py lists what each language is missing).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "src" / "frontend"
BACK = ROOT / "src" / "backend" / "app"
LANG = ROOT / "lang"
CATALOG = LANG / "catalog.json"

PAGES = [*sorted(FRONT.rglob("*.html")), *sorted((FRONT / "app" / "js").rglob("*.js")), FRONT / "common" / "pages.js"]
# the quick-capture parser reads Spanish (its words are not shown): it is not translated
SKIP_JS = {"parse.js"}
# texts of the code that are not shown (HTTP headers, CSS classes)
IGNORE = {"Vary", "Cookie, Accept-Language", "small center langrow", "Authorization", "Bearer {0}", "PRIVATE KEY",
          "btn pri", "msg info", "mamia", "Google Play"}

LETTER = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]")
SPANISH = re.compile(r"[áéíóúüñÁÉÍÓÚÜÑ¿¡]")
CODEY = re.compile(r"^[#.\-/@$&|<>()\[\]{}:;=+*%!?,0-9\s_'\"`\\]*$|[{};=]|=>|\bfunction\b|\breturn\b|\bvar\b|\bconst\b|"
                   r"\bpx\b|\brgba?\(|\bvar\(|^https?:|^data:|^\.|^#|\.(js|css|png|svg|json|html)\b|\\[nt]|^[a-z]+[A-Z]\w*$|"
                   r"^[a-z0-9_\-]+$|^[A-Z0-9_]+$|^\w+\(|\$\{|\)\.\w|\('|'\)|\?'|':'|\]\)|\}\)")
HTML_TAG = re.compile(r"<[^<>]*>")
ATTR = re.compile(r"""\b(?:placeholder|title|aria-label|alt|label|data-tip)\s*=\s*(["'])(.*?)\1""", re.S)
VAR = re.compile(r"\$\{(?:[^{}]|\{[^{}]*\})*\}")


EDGE = " \u00a0·—–-:,;|"   # lo que se quita por delante y por detrás (i18n.js hace lo mismo)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("&nbsp;", " ").replace("&amp;", "&")).strip(EDGE).lstrip(". ")


HARD = re.compile(r"NOT NULL|^//|^\^|^\[|prefers-|^#|\[data-|\$\{|''|\?'|'\}|=>|[<>]|(^|\s)[a-z]+-[a-z]+(\s|$)|\b(px|em|rem|var)\b")


def keep(s: str, html_text: bool = False) -> bool:
    if HARD.search(s):
        return False
    if len(s) < 2 or not LETTER.search(s) or len(s) > 600:
        return False
    bare = re.sub(r"\{\d\}", "", s).strip()
    if SPANISH.search(s):
        return not CODEY.search(bare) or " " in bare
    if " " in s:
        words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}", s)
        if len(words) >= 2:
            if not CODEY.search(bare):
                return True
            # frases de verdad con «;» u otros signos que el filtro de código descarta
            letters = sum(ch.isalpha() or ch == " " for ch in bare) / max(1, len(bare))
            return (len(words) >= 3 and letters > 0.8
                    and not re.search(r"=>|[{}=]|\w\(|\)\.\w|\bfunction\b|\breturn\b|\bconst\b|\bvar\b", bare))
        # «{0} meses», «el {0}», «3 meses»: una palabra junto a una cifra o un marcador (no «{0} de {1}»)
        groups = len(re.findall(r"\{\d\}(?:\s*\{\d\})*", s))   # «{0} {1}» juntos cuentan como uno
        return (len(words) == 1 and groups <= 1 and bool(re.search(r"\{\d\}|\d", s))
                and words[0].isalpha() and not re.search(r"[a-z][A-Z]", words[0]) and not re.search(r"[_#=/]", s))
    # una sola palabra: si es texto de HTML (también en minúscula: «quedan», «semanas») o empieza por mayúscula
    w = s[:-1] if s.endswith(".") else s
    if not w.isalpha() or len(w) < 2 or re.search(r"[a-z][A-Z]", w):
        return False
    if html_text:
        return len(w) >= 3 or w[:1].isupper()
    return s[:1].isupper() and not CODEY.search(w)


def renumber(p: str) -> str:
    """Cada trozo numera sus marcadores desde {0}."""
    n = iter(range(10))
    return re.sub(r"\{\d\}", lambda _m: "{%d}" % next(n, 9), p)


def fragments(text: str, html_text: bool) -> list[str]:
    """Divide por etiquetas HTML y devuelve los trozos de texto (con {n} en las partes variables)."""
    out = [m.group(2) for m in ATTR.finditer(text)] + HTML_TAG.split(text)
    res = []
    for p in out:
        p = VAR.sub("{0}", p)
        for piece in re.split(r"\s*(?:·|\||\n)\s*", p):
            c = renumber(clean(piece))
            if re.fullmatch(r"(\{\d\}\s*)+", c):
                continue
            if keep(c, html_text):
                res.append(c)
    return res


class Lexer:
    """Lector sencillo de JavaScript: saca las cadenas ('…', "…" y plantillas `…${…}…`, también anidadas) con sus
    partes variables como {0}, {1}… Si una cadena se suma con + a algo, esa parte también cuenta: 'el ' + fecha → «el {0}»."""

    def __init__(self, code: str):
        self.c, self.out = code, []

    def run(self) -> list:
        self.block(0, None)
        return self.out

    def block(self, i: int, stop):
        c, n, depth = self.c, len(self.c), 0
        while i < n:
            ch = c[i]
            if ch in "'\"":
                j = self.quoted(i)
                self.literal(i, j)
                i = j
            elif ch == "`":
                i = self.template(i)
            elif c.startswith("//", i) and (i == 0 or c[i - 1] != ":"):
                k = c.find("\n", i)
                i = n if k < 0 else k
            elif c.startswith("/*", i):
                k = c.find("*/", i + 2)
                i = n if k < 0 else k + 2
            elif ch == "/" and self.regex_ok(i):
                i = self.regex(i)
            elif ch == "{":
                depth += 1
                i += 1
            elif ch == "}":
                if depth == 0 and stop == "}":
                    return i + 1
                depth -= 1
                i += 1
            else:
                i += 1
        return n

    def regex_ok(self, i: int) -> bool:
        k = i - 1
        while k >= 0 and self.c[k] in " \t\r\n":
            k -= 1
        return k < 0 or self.c[k] in "(,=:[!&|?{};+-*%<>~^"

    def regex(self, i: int) -> int:
        c, n, k, cls = self.c, len(self.c), i + 1, False
        while k < n and c[k] != "\n":
            if c[k] == "\\":
                k += 2
                continue
            if c[k] == "[":
                cls = True
            elif c[k] == "]":
                cls = False
            elif c[k] == "/" and not cls:
                return k + 1
            k += 1
        return i + 1   # no era una expresión regular

    def quoted(self, i: int) -> int:
        c, q, k = self.c, self.c[i], i + 1
        while k < len(c) and c[k] != q and c[k] != "\n":
            k += 2 if c[k] == "\\" else 1
        return k + 1

    def literal(self, i: int, j: int) -> None:
        s = self.c[i + 1:j - 1].replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n")
        before = self.c[max(0, i - 4):i].rstrip()
        after = self.c[j:j + 4].lstrip()
        if "<" not in s and LETTER.search(s):
            self.out.append((s, False))   # también tal cual
            if before.endswith("+") and s[:1] == " ":
                s = "{0}" + s
            if after.startswith("+") and s[-1:] == " ":
                s = s + "{9}"
        self.out.append((s, "<" in s))

    def template(self, i: int) -> int:
        c, n, k, parts = self.c, len(self.c), i + 1, []
        while k < n and c[k] != "`":
            if c[k] == "\\":
                parts.append(c[k + 1:k + 2])
                k += 2
            elif c.startswith("${", k):
                k = self.block(k + 2, "}")
                parts.append("{9}")
            else:
                parts.append(c[k])
                k += 1
        s = "".join(parts)
        self.out.append((s, "<" in s))
        return k + 1


def js_strings(code: str) -> list[str]:
    out = []
    for s, html in Lexer(code).run():
        out += fragments(s, html_text=html)
    return out


def page_strings(src: str) -> list[str]:
    out = []
    pos = 0
    for m in re.finditer(r"<script\b[^>]*>(.*?)</script>|<style\b[^>]*>.*?</style>", src, re.S):
        out += fragments(src[pos:m.start()], html_text=True)
        if m.group(1) is not None:
            out += js_strings(m.group(1))
        pos = m.end()
    out += fragments(src[pos:], html_text=True)
    return out


# files whose strings are internal (prompts for the translator), not texts the users see
SKIP_PY = {"i18n.py"}
SQL = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|PRAGMA|WITH)\b", re.I)
LOGGERS = {"debug", "info", "warning", "error", "exception", "critical"}


def backend_strings() -> list[str]:
    """Textos de los mensajes de error y de los correos: cadenas y f-strings (las partes variables → {0}, {1}…)."""
    import ast
    out = []
    for p in sorted(BACK.rglob("*.py")):
        if p.name in SKIP_PY:
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        skip = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                skip.add(id(body[0].value))   # docstrings
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LOGGERS:
                for a in ast.walk(node):
                    skip.add(id(a))
        for node in ast.walk(tree):
            if id(node) in skip:
                continue
            if isinstance(node, ast.JoinedStr):
                parts, n = [], 0
                for v in node.values:
                    if isinstance(v, ast.Constant):
                        parts.append(str(v.value))
                    else:
                        parts.append("{%d}" % n); n += 1
                    skip.update(id(x) for x in ast.walk(v))
                text = "".join(parts)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            else:
                continue
            if SQL.match(text):
                continue
            out += fragments(text.replace("${", "$ {"), html_text="<" in text)
    return out


def found() -> list[str]:
    """Every Spanish text found in the code (sorted).""" 
    seen: dict[str, None] = {}
    for p in PAGES:
        if p.name in SKIP_JS:
            continue
        src = p.read_text(encoding="utf-8")
        for s in (js_strings(src) if p.suffix == ".js" else page_strings(src)):
            seen.setdefault(s, None)
    for s in backend_strings():
        seen.setdefault(s, None)
    return sorted(seen)


NEW = LANG / "new.json"


def covered(es: dict) -> set[str]:
    return {x for v in es.values() for x in (v if isinstance(v, list) else [v])}


def main() -> int:
    texts = found()
    es = json.loads((LANG / "es.json").read_text(encoding="utf-8"))
    CATALOG.write_text(json.dumps(sorted(es), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    have = covered(es)
    new = [t for t in texts if t not in have and t not in IGNORE]
    unused = sorted(k for k, v in es.items() if not set(v if isinstance(v, list) else [v]) & set(texts))
    if new:
        NEW.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{len(texts)} texts in the code; {len(new)} without an English message -> {NEW.relative_to(ROOT)}")
        for t in new[:30]:
            print("   ", t)
    else:
        NEW.unlink(missing_ok=True)
        print(f"{len(texts)} texts in the code, all in the catalog ({len(es)} English messages).")
    if unused:
        print(f"{len(unused)} messages of lang/es.json are no longer in the code (they can be removed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
