"""Encryption of the secrets kept in the database (Stripe keys, the push key, pending sign-ups).

The key comes from SECRET_KEY when it is set; otherwise the server makes a random one the first time in
<DATA_DIR>/secrets/app.key (mode 600) and reuses it. It never goes to the repository or the logs."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.core import config

_fernet: Fernet | None = None


def _key() -> bytes:
    env = os.environ.get("SECRET_KEY", "").strip()
    if env:
        return base64.urlsafe_b64encode(hashlib.sha256(env.encode()).digest())
    path = config.settings.data_dir / "secrets" / "app.key"
    if path.exists():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def _f() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_key())
    return _fernet


def reset() -> None:
    """For the tests (DATA_DIR changes)."""
    global _fernet
    _fernet = None


def encrypt(obj) -> str:
    return _f().encrypt(json.dumps(obj).encode()).decode()


def decrypt(token: str | None):
    if not token:
        return None
    try:
        return json.loads(_f().decrypt(token.encode()))
    except (InvalidToken, ValueError):
        return None


def new_token(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)
