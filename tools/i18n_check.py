#!/usr/bin/env python3
"""Checks the translations against the English catalog (lang/catalog.json, the keys of lang/es.json).

Every lang/<code>.json must translate every English message of the catalog ({"English message": "translation"}),
keeping the same {0}, {1}… placeholders. A missing translation is shown in English, so a partial file still works.
lang/es.json is checked the same way (its values are the Spanish texts of the code; lists are allowed).

Usage: python3 tools/i18n_check.py [code…]          (every language by default)
       python3 tools/i18n_check.py --part TEXTS.json TRANS.json   (a part: a list of texts and their translations)"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANG = ROOT / "lang"
PH = re.compile(r"\{\d\}")


def check(keys: list[str], tr: dict) -> list[str]:
    bad = [f"missing: {k!r}" for k in keys if k not in tr]
    for k in keys:
        v = tr.get(k)
        if v is None:
            continue
        for x in (v if isinstance(v, list) else [v]):
            if not isinstance(x, str) or not x.strip():
                bad.append(f"empty: {k!r}")
            elif sorted(PH.findall(k)) != sorted(PH.findall(x)):
                bad.append(f"placeholders differ: {k!r} -> {x!r}")
    keyset = set(keys)
    bad += [f"not in the catalog: {k!r}" for k in tr if k not in keyset]
    return bad


def main(argv: list[str]) -> int:
    if argv[:1] == ["--part"]:
        bad = check(json.loads(Path(argv[1]).read_text()), json.loads(Path(argv[2]).read_text()))
        print("\n".join(bad) or "OK")
        return 1 if bad else 0
    catalog = json.loads((LANG / "catalog.json").read_text())
    if catalog != sorted(json.loads((LANG / "es.json").read_text())):
        print("lang/catalog.json is out of date: run python3 tools/i18n_extract.py")
        rc = 1
    langs = argv or sorted(p.stem for p in LANG.glob("*.json") if p.stem not in ("catalog", "new"))
    rc = 0
    for code in langs:
        tr = json.loads((LANG / f"{code}.json").read_text())
        bad = check(catalog, tr)
        done = len(catalog) - sum(b.startswith("missing") for b in bad)
        print(f"{code}: {done}/{len(catalog)}" + (f" · {len(bad)} problems" if bad else " OK"))
        for b in bad[:20]:
            print("   ", b)
        rc |= bool(bad)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
