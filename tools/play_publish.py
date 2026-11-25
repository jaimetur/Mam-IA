#!/usr/bin/env python3
"""Upload a new version of the Android app and/or the store listing to Google Play (Play Developer API, "edits").

Used by GitHub Actions on the release branches (X.Y.Z), so nobody has to upload them by hand in Play Console:
  - android.yml uploads the AAB of each build to a test track (PLAY_TRACK, by default "alpha", the closed test);
  - play_screenshots.yml uploads the texts and images of assets/play-store/<language>/ to the listing in each language.

It signs in with a service account of the Play Console. Its JSON key is read from the environment variable
PLAY_SERVICE_ACCOUNT_JSON (the GitHub secret of the same name), never from a file of the repository.

Usage:
  python tools/play_publish.py --aab app-release.aab --track alpha --release-name "0.2.0 (45)"
  python tools/play_publish.py --listing                      # texts and images of every language in assets/play-store
  python tools/play_publish.py --listing --only en-US --dry-run

The Chromebook screenshots are not in the API: they stay in Play Console, uploaded by hand when they change.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parents[1]
LISTING_DIR = ROOT / "assets" / "play-store"
PACKAGE = "app.mamia.android"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
UPLOAD = "https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications"
# folder (or file) of assets/play-store/<language>/ → image types of the listing
IMAGES = {
    "phone": ["phoneScreenshots"],
    "tablet": ["sevenInchScreenshots", "tenInchScreenshots"],
    "feature-graphic.png": ["featureGraphic"],
}


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def access_token(sa: dict) -> str:
    """OAuth access token of the service account (a JWT signed with its key, as in app.billing.play)."""
    now = int(time.time())
    uri = sa.get("token_uri") or "https://oauth2.googleapis.com/token"
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64(json.dumps({"iss": sa["client_email"], "scope": SCOPE, "aud": uri, "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = _b64(key.sign(f"{head}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256()))
    r = requests.post(uri, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                 "assertion": f"{head}.{claims}.{sig}"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Google does not accept the service account {sa['client_email']}: {r.status_code} {r.text[:300]}")
    return r.json()["access_token"]


class Edit:
    """One Play Console edit: every change goes into it and is published together by commit()."""

    def __init__(self, token: str, package: str):
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"
        self.package = package
        r = self.call("POST", f"{API}/{package}/edits")
        self.id = r["id"]
        self.base = f"{API}/{package}/edits/{self.id}"
        self.upload_base = f"{UPLOAD}/{package}/edits/{self.id}"

    def call(self, method: str, url: str, **kw) -> dict:
        r = self.s.request(method, url, timeout=300, **kw)
        if r.status_code >= 300:
            sys.exit(f"Google Play: {method} {url.split('/applications/')[-1]} → {r.status_code}\n{r.text[:1500]}")
        return r.json() if r.content else {}

    def upload_bundle(self, aab: Path) -> int:
        with aab.open("rb") as f:
            r = self.call("POST", f"{self.upload_base}/bundles", params={"uploadType": "media"},
                          headers={"Content-Type": "application/octet-stream"}, data=f)
        return int(r["versionCode"])

    def set_track(self, track: str, version_code: int, name: str, status: str) -> None:
        release = {"name": name, "versionCodes": [str(version_code)], "status": status}
        self.call("PUT", f"{self.base}/tracks/{track}", json={"track": track, "releases": [release]})

    def set_texts(self, lang: str, title: str, short: str, full: str) -> None:
        self.call("PUT", f"{self.base}/listings/{lang}",
                  json={"language": lang, "title": title, "shortDescription": short, "fullDescription": full})

    def set_images(self, lang: str, kind: str, files: list[Path]) -> bool:
        """Replace the images of one type, unless they are already the same (same files in the same order)."""
        now = self.call("GET", f"{self.base}/listings/{lang}/{kind}").get("images", [])
        want = [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
        if [i.get("sha256") for i in now] == want:
            return False
        if now:
            self.call("DELETE", f"{self.base}/listings/{lang}/{kind}")
        for p in files:
            self.call("POST", f"{self.upload_base}/listings/{lang}/{kind}", params={"uploadType": "media"},
                      headers={"Content-Type": "image/png"}, data=p.read_bytes())
        return True

    def commit(self) -> None:
        self.call("POST", f"{self.base}:commit")


def listing_languages(only: list[str] | None) -> list[Path]:
    langs = sorted(p for p in LISTING_DIR.iterdir() if p.is_dir() and (p / "title.txt").exists())
    return [p for p in langs if not only or p.name in only]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", default=PACKAGE)
    ap.add_argument("--aab", type=Path, help="Android App Bundle to upload")
    ap.add_argument("--track", default="alpha", help="track of the release: internal, alpha (closed test), beta, production")
    ap.add_argument("--release-name", help='name of the release in Play Console, e.g. "0.2.0 (45)"')
    ap.add_argument("--status", default="completed", help="completed, or draft while the app has never been published")
    ap.add_argument("--listing", action="store_true", help="upload the texts and images of assets/play-store")
    ap.add_argument("--only", nargs="*", help="only these listing languages (e.g. en-US es-ES)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be uploaded, without signing in")
    a = ap.parse_args()
    if not a.aab and not a.listing:
        ap.error("nothing to do: give --aab and/or --listing")

    langs = listing_languages(a.only) if a.listing else []
    if a.dry_run:
        if a.aab:
            print(f"AAB {a.aab} → track {a.track} as {a.release_name!r} ({a.status})")
        for d in langs:
            n = {k: len(sorted((d / k).glob("*.png"))) if (d / k).is_dir() else int((d / k).exists()) for k in IMAGES}
            print(f"{d.name}: title {read(d / 'title.txt')!r}, images {n}")
        return

    raw = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        sys.exit("PLAY_SERVICE_ACCOUNT_JSON is empty: add the service account's JSON key as a GitHub secret.")
    edit = Edit(access_token(json.loads(raw)), a.package)

    if a.aab:
        code = edit.upload_bundle(a.aab)
        edit.set_track(a.track, code, a.release_name or str(code), a.status)
        print(f"AAB uploaded: versionCode {code} → track {a.track} ({a.release_name})")
    icon = LISTING_DIR / "icon-512.png"
    for d in langs:
        edit.set_texts(d.name, read(d / "title.txt"), read(d / "short_description.txt"), read(d / "full_description.txt"))
        changed = []
        for name, kinds in IMAGES.items():
            files = sorted((d / name).glob("*.png")) if (d / name).is_dir() else [d / name]
            for kind in kinds:
                if edit.set_images(d.name, kind, files):
                    changed.append(kind)
        if icon.exists() and edit.set_images(d.name, "icon", [icon]):
            changed.append("icon")
        print(f"{d.name}: texts updated; images replaced: {', '.join(changed) or 'none (already the same)'}")
    edit.commit()
    print("Committed to Google Play: Google reviews the changes before they are shown.")


if __name__ == "__main__":
    main()
