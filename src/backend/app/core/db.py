"""SQLite: connection, schema and the global revision counter of the families' data."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from app.core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS families (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  owner_id INTEGER,
  tz TEXT NOT NULL DEFAULT 'Europe/Madrid',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL,
  pw_hash TEXT NOT NULL,
  family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  member_id TEXT,
  role TEXT NOT NULL DEFAULT 'member',
  is_admin INTEGER NOT NULL DEFAULT 0,
  must_change INTEGER NOT NULL DEFAULT 0,
  theme TEXT NOT NULL DEFAULT 'auto',
  accent TEXT NOT NULL DEFAULT 'rosa',
  mail_reminders INTEGER NOT NULL DEFAULT 1,
  mail_digest INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  last_seen TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS family_invites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  email TEXT,
  member_id TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  used_at TEXT
);
CREATE TABLE IF NOT EXISTS password_resets (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  used_at TEXT
);
-- each family's data: one JSON document per item (events, tasks, lists, items, meals, members…); data NULL = deleted
CREATE TABLE IF NOT EXISTS docs (
  family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  collection TEXT NOT NULL,
  id TEXT NOT NULL,
  data TEXT,
  rev INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by INTEGER,
  PRIMARY KEY (family_id, collection, id)
);
CREATE INDEX IF NOT EXISTS docs_rev ON docs(family_id, rev);
CREATE TABLE IF NOT EXISTS push_subs (
  endpoint TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  keys TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS push_sent (
  family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  sent_at TEXT NOT NULL,
  PRIMARY KEY (family_id, key)
);
CREATE TABLE IF NOT EXISTS grants (
  family_id INTEGER PRIMARY KEY REFERENCES families(id) ON DELETE CASCADE,
  code TEXT,
  until_ms INTEGER,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stripe_subs (
  family_id INTEGER PRIMARY KEY REFERENCES families(id) ON DELETE CASCADE,
  customer_id TEXT NOT NULL,
  subscription_id TEXT NOT NULL UNIQUE,
  plan TEXT,
  status TEXT NOT NULL,
  period_end_ms INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  method TEXT,
  cancel_end INTEGER NOT NULL DEFAULT 0
);
-- a family's subscription bought in the Android app (Google Play): the purchase token, encrypted, and its state
CREATE TABLE IF NOT EXISTS play_subs (
  family_id INTEGER PRIMARY KEY REFERENCES families(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  token_enc TEXT NOT NULL,
  product_id TEXT,
  base_plan TEXT,
  state TEXT NOT NULL,
  expiry_ms INTEGER NOT NULL DEFAULT 0,
  checked_at INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_signups (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lapses (
  family_id INTEGER PRIMARY KEY REFERENCES families(id) ON DELETE CASCADE,
  lapsed_at TEXT NOT NULL,
  notified INTEGER NOT NULL DEFAULT 0
);
-- automatic emails already sent once (subscription notices, daily summaries…): key → when
CREATE TABLE IF NOT EXISTS mail_sent (
  key TEXT PRIMARY KEY,
  sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
-- downloads of the Android app from this server (/android.apk), per day (Administración → Negocio)
CREATE TABLE IF NOT EXISTS downloads (
  day TEXT NOT NULL,
  kind TEXT NOT NULL,
  n INTEGER NOT NULL,
  PRIMARY KEY (day, kind)
);
CREATE TABLE IF NOT EXISTS counters (
  name TEXT PRIMARY KEY,
  value INTEGER NOT NULL
);
"""

# columns added after a database was made: (table, column, definition), added when missing
MIGRATIONS = (
    ("users", "mail_reminders", "INTEGER NOT NULL DEFAULT 1"),
    ("users", "mail_digest", "INTEGER NOT NULL DEFAULT 0"),
    ("lapses", "notified", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "lang", "TEXT"),
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    path = config.settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Write transaction (BEGIN IMMEDIATE: one at a time)."""
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


@contextmanager
def ro() -> Iterator[sqlite3.Connection]:
    con = connect()
    try:
        yield con
    finally:
        con.close()


def init_db() -> None:
    con = connect()
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
        for table, column, ddl in MIGRATIONS:
            if column not in {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        # English became the language of whoever's language is not known (0.2.0): the accounts made before, when
        # Mam-IA was only in Spanish, keep Spanish (once)
        if not con.execute("SELECT 1 FROM settings WHERE key='langs_backfilled'").fetchone():
            con.execute("UPDATE users SET lang='es' WHERE lang IS NULL")
            con.execute("INSERT INTO settings(key, value) VALUES('langs_backfilled', 'true')")
    finally:
        con.close()


def get_setting(key: str, default=None):
    try:
        with ro() as con:
            r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    except sqlite3.OperationalError:
        return default
    return json.loads(r["value"]) if r else default


def set_setting(con: sqlite3.Connection, key: str, value) -> None:
    con.execute("INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)))


def count_download(kind: str = "apk") -> None:
    """One more download today (UTC). Never fails the download itself."""
    try:
        with tx() as con:
            con.execute("INSERT INTO downloads(day, kind, n) VALUES(?,?,1) ON CONFLICT(day, kind) DO UPDATE SET n = n + 1",
                        (datetime.now(timezone.utc).date().isoformat(), kind))
    except sqlite3.Error:
        pass


def next_rev(con: sqlite3.Connection) -> int:
    con.execute("INSERT INTO counters(name, value) VALUES('rev', 0) ON CONFLICT(name) DO NOTHING")
    con.execute("UPDATE counters SET value = value + 1 WHERE name='rev'")
    return con.execute("SELECT value FROM counters WHERE name='rev'").fetchone()[0]


def current_rev(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT value FROM counters WHERE name='rev'").fetchone()
    return row[0] if row else 0
