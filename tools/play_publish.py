#!/usr/bin/env python3
"""Upload a new version of the Android app and/or the store listing to Google Play (Play Developer API, "edits").

Used by GitHub Actions, so nobody has to upload them by hand in Play Console:
  - android.yml uploads the AAB of each build of a release branch (X.Y.Z) to a test track (PLAY_TRACK, by default
    "alpha", the closed test);
  - play_screenshots.yml uploads the texts and images of assets/play-store/<language>/ to the listing in each language;
  - release.yml, on every push to main, promotes the version's build from the closed test to the stable track
    (PLAY_STABLE_TRACK, e.g. "production"): the same build the testers had, without building it again.
Every release takes its notes ("What's new") from the version's block in CHANGELOG.md (release_notes()).

It signs in with a service account of the Play Console. Its JSON key is read from the environment variable
PLAY_SERVICE_ACCOUNT_JSON (the GitHub secret of the same name), never from a file of the repository.

Usage:
  python tools/play_publish.py --aab app-release.aab --track alpha --release-name "0.2.0 (45)" --version 0.2.0
  python tools/play_publish.py --listing                      # texts and images of every language in assets/play-store
  python tools/play_publish.py --listing --only en-US --dry-run
  python tools/play_publish.py --promote --version 0.2.0 --from-track alpha --track production
  python tools/play_publish.py --promote --version 0.2.0 --dry-run      # shows the release notes Play would get

The Chromebook screenshots are not in the API: they stay in Play Console, uploaded by hand when they change.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parents[1]
LISTING_DIR = ROOT / "assets" / "play-store"
PACKAGE = "app.mamia.android"
CHANGELOG = ROOT / "CHANGELOG.md"
CHANGELOG_LANG = "en-US"  # the language CHANGELOG.md is written in
NOTES_MAX = 500  # Play's limit for the release notes of each language
USER_SECTIONS = ("🌟", "🚀", "🐛")
RETRIES, RETRY_WAIT = 3, 30  # a change committed meanwhile to the same app (another workflow) deletes this one: start again


class EditDeleted(Exception):
    """Google Play deleted the open edit because another one was committed meanwhile (e.g. the listing and the AAB)."""


def _failed(r, what: str):
    if r.status_code == 400 and "This Edit has been deleted" in r.text:
        raise EditDeleted(what)
    sys.exit(f"Google Play: {what} → {r.status_code}\n{r.text[:1500]}")  # sections of a changelog block that users notice: new, better, fixed
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
            _failed(r, f"{method} {url.split('/applications/')[-1]}")
        return r.json() if r.content else {}

    def upload_bundle(self, aab: Path) -> int:
        with aab.open("rb") as f:
            r = self.call("POST", f"{self.upload_base}/bundles", params={"uploadType": "media"},
                          headers={"Content-Type": "application/octet-stream"}, data=f)
        return int(r["versionCode"])

    def set_track(self, track: str, codes: list[str], name: str, status: str, notes: dict[str, str]) -> None:
        """Make this the only release of the track, with the notes of the languages the listing has."""
        have = self.languages()
        for lang in sorted(set(notes) - have):
            print(f"Release notes in {lang} skipped: the listing has no {lang} translation")
        release = {"name": name, "versionCodes": codes, "status": status,
                   "releaseNotes": [{"language": k, "text": v} for k, v in sorted(notes.items()) if k in have]}
        self.call("PUT", f"{self.base}/tracks/{track}", json={"track": track, "releases": [release]})

    def languages(self) -> set[str]:
        return {x["language"] for x in self.call("GET", f"{self.base}/listings").get("listings", [])}

    def releases(self, track: str) -> list[dict]:
        """Releases of a track (none if the track has never had one)."""
        r = self.s.get(f"{self.base}/tracks/{track}", timeout=60)
        if r.status_code == 404:
            return []
        if r.status_code >= 300:
            _failed(r, f"GET tracks/{track}")
        return r.json().get("releases", [])

    def discard(self) -> None:
        self.s.delete(self.base, timeout=60)

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


def release_notes(version: str) -> dict[str, str]:
    """Play's "What's new" for a version, by language, from its block in CHANGELOG.md.

    Its "#### 📱 Google Play (<language>):" sections as they are (one per language, e.g. "(es-ES)"); without them, the
    titles of its new features, enhancements and fixes, one per line, in the changelog's language. At most 500
    characters per language, as Play allows."""
    m = re.search(rf"^## Release: v{re.escape(version)}\s*$(.*?)(?=^---\s*$|^## |\Z)",
                  CHANGELOG.read_text(encoding="utf-8"), re.M | re.S)
    if not m:
        return {}
    sections = re.findall(r"^#### (.*?)\n(.*?)(?=^#### |\Z)", m.group(1), re.M | re.S)
    own = {}
    for head, body in sections:
        lang = re.match(r"📱 Google Play \(([\w-]+)\):?$", head.strip())
        if lang and body.strip():
            text = body.strip()
            own[lang.group(1)] = text if len(text) <= NOTES_MAX else text[:NOTES_MAX - 1].rstrip() + "…"
    if own:
        return own
    lines: list[str] = []
    for head, body in sections:
        if not head.startswith(USER_SECTIONS):
            continue
        for item in re.findall(r"^- (.+)$", body, re.M):
            bold = re.match(r"\*\*(.+?)\*\*", item)
            title = bold.group(1) if bold else re.split(r"(?<=[.:;])\s|\s\(", item, maxsplit=1)[0]
            title = re.sub(r"[*`]", "", title).strip().rstrip(".:;,")
            if len(title) > 120:
                title = title[:119].rstrip() + "…"
            if title and len("\n".join(lines + [f"• {title}"])) <= NOTES_MAX:
                lines.append(f"• {title}")
    return {CHANGELOG_LANG: "\n".join(lines)} if lines else {}


def promote(edit: Edit, version: str, source: str, target: str, notes: dict[str, str]) -> bool:
    """Put the build of `version` that is on the `source` track (its release is named "X.Y.Z (N)") on the `target`
    track too, for every user, with `notes`. False if it is already there."""
    found = [r for r in edit.releases(source) if r.get("name", "").startswith(f"{version} (") and r.get("versionCodes")]
    if not found:
        names = ", ".join(r.get("name", "?") for r in edit.releases(source)) or "nothing"
        sys.exit(f"Google Play: the {source} track has no {version} build (it has: {names}). Run the Android workflow on "
                 f"the {version} branch first, so that it reaches the {source} track.")
    rel = max(found, key=lambda r: max(int(c) for c in r["versionCodes"]))
    if any(r.get("versionCodes") == rel["versionCodes"] for r in edit.releases(target)):
        print(f"{rel['name']} is already on the {target} track: nothing to do.")
        return False
    edit.set_track(target, rel["versionCodes"], rel["name"], "completed", notes)
    print(f"{rel['name']}: from the {source} track to the {target} track")
    return True


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
    ap.add_argument("--version", help="X.Y.Z: its block in CHANGELOG.md gives the release notes")
    ap.add_argument("--promote", action="store_true", help="put the --version build of --from-track on --track")
    ap.add_argument("--from-track", default="alpha", help="track the build to promote is on (default alpha)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be uploaded, without signing in")
    a = ap.parse_args()
    if not a.aab and not a.listing and not a.promote:
        ap.error("nothing to do: give --aab, --listing or --promote")
    if a.promote and (a.aab or a.listing or not a.version):
        ap.error("--promote goes on its own, with --version")

    langs = listing_languages(a.only) if a.listing else []
    notes = release_notes(a.version) if a.version else {}
    if a.dry_run:
        if a.promote:
            print(f"{a.version}: from the {a.from_track} track to the {a.track} track")
        for lang, text in notes.items():
            print(f"Release notes ({lang}, {len(text)} characters):\n{text}")
        if a.aab:
            print(f"AAB {a.aab} → track {a.track} as {a.release_name!r} ({a.status})")
        for d in langs:
            n = {k: len(sorted((d / k).glob("*.png"))) if (d / k).is_dir() else int((d / k).exists()) for k in IMAGES}
            print(f"{d.name}: title {read(d / 'title.txt')!r}, images {n}")
        return

    raw = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        sys.exit("PLAY_SERVICE_ACCOUNT_JSON is empty: add the service account's JSON key as a GitHub secret.")
    token = access_token(json.loads(raw))
    for attempt in range(1, RETRIES + 1):
        try:
            return publish(Edit(token, a.package), a, notes, langs)
        except EditDeleted as e:
            if attempt == RETRIES:
                sys.exit(f"Google Play deleted the edit {RETRIES} times ({e}): another change to the app kept being committed.")
            print(f"Google Play deleted the edit ({e}): another change was committed meanwhile; again in {RETRY_WAIT * attempt} s")
            time.sleep(RETRY_WAIT * attempt)


def publish(edit: Edit, a, notes: dict[str, str], langs: list[Path]) -> None:
    """Everything that goes to Google Play in one edit: the promotion, or the AAB and/or the listing."""
    if a.promote:
        if promote(edit, a.version, a.from_track, a.track, notes):
            edit.commit()
            print("Committed to Google Play: Google reviews the version before it is shown.")
        else:
            edit.discard()
        return
    if a.aab:
        code = edit.upload_bundle(a.aab)
        edit.set_track(a.track, [str(code)], a.release_name or str(code), a.status, notes)
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
