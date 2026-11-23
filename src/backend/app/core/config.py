"""Settings read from environment variables (never secrets in the code)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# repository root (src/backend/app/core/config.py → ../../../..)
ROOT = Path(__file__).resolve().parents[4]


def _bool(v: str | None, default: bool) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "si", "sí", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("DATA_DIR", "/data")))
    frontend_dir: Path = field(default_factory=lambda: Path(os.environ.get("FRONTEND_DIR", str(ROOT / "src" / "frontend"))))
    lang_dir: Path = field(default_factory=lambda: Path(os.environ.get("I18N_DIR", str(ROOT / "lang"))))
    branding_dir: Path = field(default_factory=lambda: Path(os.environ.get("BRANDING_DIR", str(ROOT / "assets" / "branding"))))
    docs_dir: Path = field(default_factory=lambda: Path(os.environ.get("DOCS_DIR", str(ROOT))))
    # public address, without the final slash (links in emails and Stripe's return pages)
    public_url: str = field(default_factory=lambda: os.environ.get("PUBLIC_URL", "").rstrip("/"))
    # "Secure" cookies unless turned off on purpose (development on http://localhost)
    cookie_secure: bool = field(default_factory=lambda: _bool(os.environ.get("COOKIE_SECURE"), True))
    session_days: int = field(default_factory=lambda: _int("SESSION_DAYS", 180))
    invite_days: int = field(default_factory=lambda: _int("INVITE_DAYS", 14))
    scheduler_enabled: bool = field(default_factory=lambda: _bool(os.environ.get("SCHEDULER_ENABLED"), True))
    # families can be created without paying (development, or a private server for one's own family)
    open_signup: bool = field(default_factory=lambda: _bool(os.environ.get("OPEN_SIGNUP"), False))
    # the server administrator's account, made once with an empty database (the password must be changed on entering)
    admin_email: str = field(default_factory=lambda: os.environ.get("MAMIA_ADMIN_EMAIL", "").strip())
    admin_name: str = field(default_factory=lambda: os.environ.get("MAMIA_ADMIN_NAME", "Administración").strip())
    admin_password: str = field(default_factory=lambda: os.environ.get("MAMIA_ADMIN_PASSWORD", "mamia-cambiar"))
    admin_family: str = field(default_factory=lambda: os.environ.get("MAMIA_ADMIN_FAMILY", "Mi familia").strip())
    contact_email: str = field(default_factory=lambda: os.environ.get("MAMIA_CONTACT_EMAIL", "mamia@jtgcloud.com").strip())
    timezone: str = field(default_factory=lambda: os.environ.get("TZ", "Europe/Madrid") or "Europe/Madrid")
    # where the Android APK is taken from when the server has no copy (<DATA_DIR>/android/mamia-android.apk)
    android_url: str = field(default_factory=lambda: os.environ.get(
        "ANDROID_APK_URL", "https://github.com/jaimetur/Mam-IA/releases/download/android-latest/mamia-android.apk"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "mamia.db"


settings = Settings()


def reload_settings() -> Settings:
    """Read the environment again (for the tests)."""
    global settings
    settings = Settings()
    return settings
