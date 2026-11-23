"""What each collection of a family's data may hold. The server keeps only the known fields, with their types and
sizes checked, so a broken or malicious client cannot store anything else.

Field types: "str:N" (text up to N characters), "text" (up to 4000), "date" (YYYY-MM-DD), "time" (HH:MM),
"when" (YYYY-MM-DD or YYYY-MM-DDTHH:MM), "bool", "int:MIN:MAX", "id" (another document's id), "ids:N" (up to N ids),
"enum:a|b", "strs:N:M" (up to N texts of up to M characters), "dates:N", "rule" (a repetition), "obj:N" (a small
object of texts, up to N keys) and "json:BYTES" (free JSON, up to BYTES). A "!" after the type makes it required."""
from __future__ import annotations

import json
import re

ID_RE = re.compile(r"^[A-Za-z0-9_:.\-]{1,64}$")
DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
COLORS = "c1|c2|c3|c4|c5|c6|c7|c8"
CATS = "casa|peques|cole|salud|trabajo|compras|comidas|ocio|pareja|yo|papeleo|otros"
MAX_DOC_BYTES = 16_000
MAX_MEMBERS = 8
MAX_DOCS_PER_FAMILY = 50_000

SPEC: dict[str, dict[str, str]] = {
    # the people of the family: adults (with or without an account) and kids (profiles); "userId" is set by the server
    "members": {"name": "str:40!", "kind": "enum:adult|kid", "color": f"enum:{COLORS}", "birthday": "date",
                "info": "obj:30", "order": "int:0:99"},
    "events": {"title": "str:120!", "start": "when!", "end": "when", "allDay": "bool", "who": "ids:8", "driver": "id",
               "pickup": "id", "place": "str:120", "notes": "text", "cat": f"enum:{CATS}", "repeat": "rule",
               "remind": "int:0:20160", "exdates": "dates:400"},
    "tasks": {"title": "str:160!", "who": "id", "due": "date", "time": "time", "done": "bool", "doneAt": "str:40",
              "doneBy": "id", "cat": f"enum:{CATS}", "repeat": "rule", "rotate": "ids:8", "remind": "int:0:20160",
              "notes": "text", "prio": "enum:normal|alta"},
    # one per task done (also each time a repeating task is done): the family's load balance comes from them
    "done": {"task": "id", "title": "str:160!", "by": "id", "date": "date!", "cat": f"enum:{CATS}"},
    "lists": {"name": "str:60!", "kind": "enum:compra|otra", "order": "int:0:999"},
    "items": {"list": "id!", "text": "str:120!", "qty": "str:20", "section": "str:40", "done": "bool", "by": "id",
              "src": "enum:manual|menu|siempre", "order": "int:0:99999", "note": "str:120"},
    # "lo de siempre": what is bought every week, added to a list in one tap
    "staples": {"text": "str:120!", "section": "str:40", "list": "id"},
    "meals": {"date": "date!", "slot": "enum:comida|cena!", "dish": "str:120", "school": "str:120",
              "ingredients": "strs:30:60"},
    "notes": {"title": "str:120", "text": "text", "pinned": "bool"},
    # family-wide preferences (shop sections, default reminders…)
    "prefs": {"value": "json:8000"},
}
SECTIONS_DEFAULT = ["Fruta y verdura", "Carne y pescado", "Lácteos y huevos", "Panadería", "Despensa", "Congelados",
                    "Bebidas", "Droguería", "Higiene", "Bebé", "Otros"]


class Invalid(ValueError):
    """A document that does not fit its collection."""


def _req(kind: str) -> tuple[str, bool]:
    return (kind[:-1], True) if kind.endswith("!") else (kind, False)


def _rule(v) -> dict | None:
    if v in (None, "", {}):
        return None
    if not isinstance(v, dict) or v.get("freq") not in ("daily", "weekly", "monthly", "yearly"):
        raise Invalid("La repetición no es válida.")
    every = v.get("every", 1)
    if not isinstance(every, int) or isinstance(every, bool) or not 1 <= every <= 52:
        raise Invalid("La repetición no es válida.")
    out = {"freq": v["freq"], "every": every}
    if v["freq"] == "weekly":
        days = v.get("days") or []
        if not isinstance(days, list) or any(not isinstance(d, int) or isinstance(d, bool) or not 0 <= d <= 6 for d in days):
            raise Invalid("Los días de la repetición no son válidos.")
        out["days"] = sorted(set(days))
    until = v.get("until")
    if until:
        if not isinstance(until, str) or not DATE_RE.match(until):
            raise Invalid("La fecha final de la repetición no es válida.")
        out["until"] = until
    return out


def _value(name: str, kind: str, v):
    """The value cleaned for its type, or None when empty. Raises Invalid when it does not fit."""
    base, _, arg = kind.partition(":")
    if v is None or (isinstance(v, str) and not v.strip() and base not in ("bool",)):
        return None
    if base == "str":
        if not isinstance(v, (str, int, float)) or isinstance(v, bool):
            raise Invalid(f"«{name}» no es un texto.")
        s = " ".join(str(v).split())
        if len(s) > int(arg):
            raise Invalid(f"«{name}» es demasiado largo (máximo {arg} caracteres).")
        return s or None
    if base == "text":
        if not isinstance(v, str):
            raise Invalid(f"«{name}» no es un texto.")
        s = v.strip().replace("\r\n", "\n")
        if len(s) > 4000:
            raise Invalid(f"«{name}» es demasiado largo.")
        return s or None
    if base == "date":
        if not isinstance(v, str) or not DATE_RE.match(v):
            raise Invalid(f"«{name}» no es una fecha.")
        return v
    if base == "time":
        if not isinstance(v, str) or not TIME_RE.match(v):
            raise Invalid(f"«{name}» no es una hora.")
        return v
    if base == "when":
        if not isinstance(v, str) or not (DATE_RE.match(v[:10]) and (len(v) == 10 or (len(v) == 16 and v[10] == "T" and TIME_RE.match(v[11:])))):
            raise Invalid(f"«{name}» no es una fecha y hora.")
        return v
    if base == "bool":
        if not isinstance(v, bool):
            raise Invalid(f"«{name}» tiene que ser sí o no.")
        return v
    if base == "int":
        lo, hi = (int(x) for x in arg.split(":"))
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise Invalid(f"«{name}» no es un número válido.")
        return v
    if base == "id":
        if not isinstance(v, str) or not ID_RE.match(v):
            raise Invalid(f"«{name}» no es válido.")
        return v
    if base == "ids":
        if not isinstance(v, list) or len(v) > int(arg) or any(not isinstance(x, str) or not ID_RE.match(x) for x in v):
            raise Invalid(f"«{name}» no es válido.")
        return list(dict.fromkeys(v)) or None
    if base == "enum":
        if v not in arg.split("|"):
            raise Invalid(f"«{name}» no es válido.")
        return v
    if base == "strs":
        n, m = (int(x) for x in arg.split(":"))
        if not isinstance(v, list) or len(v) > n or any(not isinstance(x, str) or len(x.strip()) > m for x in v):
            raise Invalid(f"«{name}» no es válido.")
        return [x.strip() for x in v if x.strip()] or None
    if base == "dates":
        if not isinstance(v, list) or len(v) > int(arg) or any(not isinstance(x, str) or not DATE_RE.match(x) for x in v):
            raise Invalid(f"«{name}» no es válido.")
        return sorted(set(v)) or None
    if base == "rule":
        return _rule(v)
    if base == "obj":
        if not isinstance(v, dict) or len(v) > int(arg):
            raise Invalid(f"«{name}» no es válido.")
        out = {}
        for k, x in v.items():
            if not isinstance(k, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", k):
                raise Invalid(f"«{name}» no es válido.")
            if x in (None, ""):
                continue
            if not isinstance(x, str) or len(x) > 1000:
                raise Invalid(f"«{name}.{k}» no es válido.")
            out[k] = x.strip()
        return out or None
    if base == "json":
        size = len(json.dumps(v, ensure_ascii=False).encode())
        if size > int(arg):
            raise Invalid(f"«{name}» es demasiado grande.")
        return v
    raise Invalid(f"Tipo desconocido para «{name}».")


def clean(collection: str, data) -> dict:
    """The document as it will be stored: only the known fields, each one checked."""
    spec = SPEC.get(collection)
    if spec is None:
        raise Invalid("Esa colección no existe.")
    if not isinstance(data, dict):
        raise Invalid("El documento no es válido.")
    out = {}
    for name, kind in spec.items():
        base, required = _req(kind)
        v = _value(name, base, data.get(name))
        if v is None:
            if required:
                raise Invalid(f"Falta «{name}».")
            continue
        out[name] = v
    if collection == "members":
        out.setdefault("kind", "adult")
        out.setdefault("color", "c1")
    if len(json.dumps(out, ensure_ascii=False).encode()) > MAX_DOC_BYTES:
        raise Invalid("El documento es demasiado grande.")
    return out
