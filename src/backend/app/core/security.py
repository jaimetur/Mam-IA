"""Passwords (argon2), tokens and limits on failed attempts."""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher()
# a padding hash, so a missing account takes as long as a wrong password
_DUMMY = _ph.hash("mamia-relleno")

MIN_PASSWORD = 8


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw_hash: str | None, pw: str) -> bool:
    try:
        return _ph.verify(pw_hash or _DUMMY, pw) and pw_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_problem(pw: str) -> str | None:
    if len(pw or "") < MIN_PASSWORD:
        return f"La contraseña tiene que tener al menos {MIN_PASSWORD} caracteres."
    if len(pw) > 200:
        return "La contraseña es demasiado larga."
    return None


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


class Throttle:
    """Sliding window in memory: at most `limit` failures per key every `window` seconds."""

    def __init__(self, limit: int = 8, window: float = 900.0):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, time.monotonic())) >= self.limit

    def fail(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


login_throttle = Throttle()
# password reset and invitation emails: a few per address and hour
mail_throttle = Throttle(limit=5, window=3600.0)
