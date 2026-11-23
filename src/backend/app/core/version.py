"""Version of the code the server is serving: the build (commit, from the image) and the release (CHANGELOG.md)."""
from __future__ import annotations

import os
import re
from functools import lru_cache

from app.core import config


def build() -> str:
    """The commit of the image (MAMIA_REVISION); "dev" when running from the repository."""
    return os.environ.get("MAMIA_REVISION", "dev") or "dev"


@lru_cache(maxsize=1)
def release() -> dict:
    """Version and date of the current release: the first «## Release: vX.Y.Z» and «### Release Date:» of CHANGELOG.md."""
    try:
        txt = (config.settings.docs_dir / "CHANGELOG.md").read_text(encoding="utf-8")[:6000]
    except OSError:
        return {"version": None, "releaseDate": None}
    v = re.search(r"^## Release: v?([0-9][\w.\-]*)", txt, re.M)
    d = re.search(r"^### Release Date: *(\d{4}-\d{2}-\d{2})", txt, re.M)
    return {"version": v.group(1) if v else None, "releaseDate": d.group(1) if d else None}


def current() -> dict:
    return {"build": build(), **release()}


def stamp() -> str:
    """What goes in the URLs of the static files (?v=…) so browsers fetch them again after an update."""
    b = build()
    if b != "dev":
        return b[:12]
    return (release()["version"] or "dev") + "-dev"
