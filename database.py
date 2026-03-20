import sqlite3
from flask import g, current_app


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            phone       TEXT NOT NULL,
            address     TEXT NOT NULL,
            id_type     TEXT NOT NULL,
            id_number   TEXT NOT NULL,
            member_type TEXT NOT NULL DEFAULT 'General',
            joined_on   DATE NOT NULL DEFAULT (date('now')),
            is_active   INTEGER NOT NULL DEFAULT 1,
            notes       TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS books (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
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
        CREATE INDEX IF NOT EXISTS idx_issues_open    ON issues(returned_on) WHERE returned_on IS NULL;
    """)
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
