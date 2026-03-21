import os
import re
import sqlite3
from flask import g, current_app

_DATABASE_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = _DATABASE_URL.startswith(("postgresql://", "postgres://"))
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
# Use HTTPS RPC when Supabase creds are present (avoids IPv6-only direct connection)
_USE_RPC = bool(_IS_PG and _SUPABASE_URL and _SUPABASE_KEY)


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


# ── psycopg2 / SQLite cursor wrapper ──────────────────────────────────────────

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
    """Unified database wrapper for both SQLite and PostgreSQL (psycopg2)."""

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


# ── Supabase RPC (HTTPS) wrapper ───────────────────────────────────────────────

class _RpcCursor:
    """Cursor-like object backed by the JSON result of run_query()."""

    def __init__(self, data):
        self._rows = []
        self._lastrowid = None
        if isinstance(data, list):
            self._rows = [_Row(r) if isinstance(r, dict) else r for r in data]
        elif isinstance(data, dict):
            if "lastrowid" in data:
                self._lastrowid = data["lastrowid"]
            # rowcount / ok results have no rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    @property
    def lastrowid(self):
        return self._lastrowid


class _NoopConn:
    """Stub connection used so init_db() can call db._conn.rollback() safely."""
    def rollback(self): pass


class _SupabaseRPC:
    """Database interface that executes SQL via Supabase's run_query() RPC over HTTPS.

    This avoids the need for a direct TCP connection to the PostgreSQL database,
    which is problematic on Vercel serverless (IPv6-only Supabase direct host,
    connection pooler not yet provisioned for new projects).
    """

    def __init__(self, url, key):
        self._rpc_url = url.rstrip("/") + "/rest/v1/rpc/run_query"
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        self._conn = _NoopConn()  # for init_db()'s db._conn.rollback() calls

    def execute(self, sql, params=()):
        import json as _json
        import urllib.request
        import urllib.error

        # Skip SQLite-specific statements that don't apply on PostgreSQL
        sql_stripped = sql.strip()
        if sql_stripped.upper().startswith("PRAGMA"):
            return _RpcCursor([])

        # Convert ? placeholders to $1, $2, ...
        count = [0]
        def _replace(_m):
            count[0] += 1
            return f"${count[0]}"
        pg_sql = re.sub(r"\?", _replace, sql_stripped)

        payload = _json.dumps({
            "q": pg_sql,
            "p": [str(v) if v is not None else None for v in params],
        }).encode("utf-8")

        req = urllib.request.Request(
            self._rpc_url, data=payload, headers=self._headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = _json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DB RPC error {e.code}: {body}")

        return _RpcCursor(result)

    def executescript(self, script):
        pass  # Schema is managed via Supabase MCP migrations

    def commit(self):
        pass  # Auto-committed via REST API

    def close(self):
        pass


# ── URL parser for psycopg2 fallback ──────────────────────────────────────────

def _parse_pg_url(url):
    """Parse a PostgreSQL URL robustly, handling @ in passwords."""
    from urllib.parse import unquote
    rest = url.split("://", 1)[1]
    rest, _, query = rest.partition("?")
    if "/" in rest:
        rest, _, dbname = rest.partition("/")
    else:
        dbname = "postgres"
    at = rest.rfind("@")
    if at != -1:
        credentials, host_port = rest[:at], rest[at + 1:]
    else:
        credentials, host_port = "", rest
    if ":" in host_port:
        host, port_str = host_port.rsplit(":", 1)
        port = int(port_str) if port_str.isdigit() else 5432
    else:
        host, port = host_port, 5432
    colon = credentials.find(":")
    if colon != -1:
        user = unquote(credentials[:colon])
        password = unquote(credentials[colon + 1:])
    else:
        user, password = unquote(credentials), ""
    # Rewrite Supabase direct host (IPv6-only) to pooler (IPv4)
    direct_match = re.match(r"db\.([^.]+)\.supabase\.co", host)
    if direct_match:
        project_ref = direct_match.group(1)
        region = os.environ.get("SUPABASE_REGION", "ap-south-1")
        host = f"aws-0-{region}.pooler.supabase.com"
        port = 5432
        if "." not in user:
            user = f"{user}.{project_ref}"
    params = {"host": host, "port": port, "user": user, "password": password,
              "dbname": dbname or "postgres", "sslmode": "require",
              "connect_timeout": 10}
    if query:
        for part in query.split("&"):
            k, _, v = part.partition("=")
            if k and k not in params:
                params[k] = v
    return params


# ── Public API ─────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        if _USE_RPC:
            # Supabase HTTPS RPC — works on Vercel serverless without TCP
            g.db = _SupabaseRPC(_SUPABASE_URL, _SUPABASE_KEY)
        elif _IS_PG:
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
        # Schema already applied to Supabase via MCP migrations.
        # Run incremental migrations — silently skip if columns already exist.
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

    # Incremental migrations for existing SQLite databases
    existing_member_cols = [row[1] for row in db.execute("PRAGMA table_info(members)").fetchall()]
    existing_book_cols = [row[1] for row in db.execute("PRAGMA table_info(books)").fetchall()]
    if "member_code" not in existing_member_cols:
        db.execute("ALTER TABLE members ADD COLUMN member_code TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_member_code ON members(member_code)")
    if "book_code" not in existing_book_cols:
        db.execute("ALTER TABLE books ADD COLUMN book_code TEXT")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_book_code ON books(book_code)")
    db.execute("UPDATE members SET member_code = 'MEM-' || printf('%04d', id) WHERE member_code IS NULL")
    db.execute("UPDATE books SET book_code = 'BOOK-' || printf('%04d', id) WHERE book_code IS NULL")
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
