import os
import sqlite3
from flask import g, current_app

_DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = _DATABASE_URL.startswith(("postgresql://", "postgres://"))


class _Row(dict):
    """Dict subclass that also supports attribute-style access."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)

    def keys(self):
        return super().keys()


class _Cursor:
    """Normalises psycopg2 / sqlite3 cursor so routes see the same API."""

    def __init__(self, raw, is_pg=False):
        self._raw = raw
        self._is_pg = is_pg

    def fetchone(self):
        row = self._raw.fetchone()
        if row is None:
            return None
        if self._is_pg:
            return _Row(row)
        return row   # sqlite3.Row already supports dict-like access

    def fetchall(self):
        rows = self._raw.fetchall()
        if self._is_pg:
            return [_Row(r) for r in rows]
        return rows

    @property
    def lastrowid(self):
        if self._is_pg:
            return self._raw.fetchone()["id"] if self._raw.rowcount > 0 else None
        return self._raw.lastrowid


class _DB:
    """Unified database wrapper for both SQLite and PostgreSQL."""

    def __init__(self, conn, is_pg=False):
        self._conn = conn
        self._is_pg = is_pg
        if is_pg:
            import psycopg2.extras
            self._cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def execute(self, sql, params=()):
        if self._is_pg:
            sql = sql.replace("?", "%s")
            self._cur.execute(sql, params if params else None)
            return _Cursor(self._cur, is_pg=True)
        else:
            raw = self._conn.execute(sql, params)
            return _Cursor(raw, is_pg=False)

    def executescript(self, script):
        if self._is_pg:
            self._cur.execute(script)
        else:
            self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def _parse_pg_url(url):
    """Parse a PostgreSQL URL robustly, handling @ in passwords.

    Standard urlparse fails when the password contains an unencoded '@'.
    We find the LAST '@' before the host to correctly split credentials.
    """
    from urllib.parse import unquote
    # Strip scheme
    rest = url.split("://", 1)[1]
    # Split off query string
    rest, _, query = rest.partition("?")
    # Split off path (dbname)
    if "/" in rest:
        rest, _, dbname = rest.partition("/")
    else:
        dbname = "postgres"
    # Split credentials from host using LAST '@'
    at = rest.rfind("@")
    if at != -1:
        credentials, host_port = rest[:at], rest[at + 1:]
    else:
        credentials, host_port = "", rest
    # Parse host:port
    if ":" in host_port:
        host, port_str = host_port.rsplit(":", 1)
        port = int(port_str) if port_str.isdigit() else 5432
    else:
        host, port = host_port, 5432
    # Parse user:password (split on FIRST ':' only)
    colon = credentials.find(":")
    if colon != -1:
        user = unquote(credentials[:colon])
        password = unquote(credentials[colon + 1:])
    else:
        user, password = unquote(credentials), ""
    params = {"host": host, "port": port, "user": user, "password": password,
              "dbname": dbname or "postgres", "sslmode": "require",
              "connect_timeout": 10}
    # Merge any extra query params (e.g. pgbouncer=true)
    if query:
        for part in query.split("&"):
            k, _, v = part.partition("=")
            if k and k not in params:
                params[k] = v
    return params


def get_db() -> _DB:
    if "db" not in g:
        if _IS_PG:
            import psycopg2
            conn = psycopg2.connect(**_parse_pg_url(_DATABASE_URL))
            g.db = _DB(conn, is_pg=True)
        else:
            conn = sqlite3.connect(current_app.config["DATABASE"])
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db = _DB(conn, is_pg=False)
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.commit()
        except Exception:
            pass
        db.close()


def init_db():
    db = get_db()
    if _IS_PG:
        # Schema already applied to Supabase via MCP migrations
        # Run incremental migrations (no-op if columns already exist)
        for sql in [
            "ALTER TABLE members ADD COLUMN doc_filename TEXT",
            "ALTER TABLE members ADD COLUMN member_code TEXT UNIQUE",
            "ALTER TABLE books ADD COLUMN book_code TEXT UNIQUE",
        ]:
            try:
                db.execute(sql)
                db.commit()
            except Exception:
                db._conn.rollback()
        # Backfill codes for existing rows
        db.execute("UPDATE members SET member_code = 'MEM-' || LPAD(id::text, 4, '0') WHERE member_code IS NULL")
        db.execute("UPDATE books SET book_code = 'BOOK-' || LPAD(id::text, 4, '0') WHERE book_code IS NULL")
        db.commit()
        return

    db.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            member_code TEXT,
            name        TEXT NOT NULL,
            phone       TEXT NOT NULL,
            address     TEXT NOT NULL,
            id_type     TEXT NOT NULL,
            id_number   TEXT NOT NULL,
            member_type TEXT NOT NULL DEFAULT 'General',
            joined_on   DATE NOT NULL DEFAULT (date('now')),
            is_active   INTEGER NOT NULL DEFAULT 1,
            notes       TEXT,
            doc_filename TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS books (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            book_code     TEXT,
            title         TEXT NOT NULL,
            author        TEXT NOT NULL,
            isbn          TEXT,
            publisher     TEXT,
            year          INTEGER,
            category      TEXT NOT NULL,
            rack_location TEXT,
            total_copies  INTEGER NOT NULL DEFAULT 1,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS issues (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id       INTEGER NOT NULL REFERENCES books(id),
            member_id     INTEGER NOT NULL REFERENCES members(id),
            issued_on     DATE NOT NULL DEFAULT (date('now')),
            due_date      DATE NOT NULL,
            returned_on   DATE,
            reissue_count INTEGER NOT NULL DEFAULT 0,
            issued_by     TEXT,
            notes         TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_members_name   ON members(name);
        CREATE INDEX IF NOT EXISTS idx_members_phone  ON members(phone);
        CREATE INDEX IF NOT EXISTS idx_books_title    ON books(title);
        CREATE INDEX IF NOT EXISTS idx_books_author   ON books(author);

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'staff',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (date('now')),
            reset_token TEXT,
            reset_token_expiry TEXT
        );
    """)
    db.commit()

    # Incremental migrations — add new columns to existing databases (no-op if already present)
    existing_member_cols = [row[1] for row in db.execute("PRAGMA table_info(members)").fetchall()]
    existing_book_cols = [row[1] for row in db.execute("PRAGMA table_info(books)").fetchall()]
    if "member_code" not in existing_member_cols:
        db.execute("ALTER TABLE members ADD COLUMN member_code TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_member_code ON members(member_code)")
    if "book_code" not in existing_book_cols:
        db.execute("ALTER TABLE books ADD COLUMN book_code TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_book_code ON books(book_code)")
    # Backfill codes for existing rows that don't have one yet
    db.execute("UPDATE members SET member_code = 'MEM-' || printf('%04d', id) WHERE member_code IS NULL")
    db.execute("UPDATE books SET book_code = 'BOOK-' || printf('%04d', id) WHERE book_code IS NULL")
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
