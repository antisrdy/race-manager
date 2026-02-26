import os
import sqlite3

DATABASE      = os.environ.get('DATABASE', 'race_manager.db')
SCHEMA_VERSION = 3   # increment when schema changes (triggers auto-migration)


def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current != SCHEMA_VERSION:
        conn.executescript("""
            DROP TABLE IF EXISTS finish_times;
            DROP TABLE IF EXISTS runners;
            DROP TABLE IF EXISTS races;
        """)

    conn.executescript(f"""
        PRAGMA user_version = {SCHEMA_VERSION};

        CREATE TABLE IF NOT EXISTS races (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            start_time TEXT,          -- NULL until the organiser sets it
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Bib numbers are globally unique across all races.
        CREATE TABLE IF NOT EXISTS runners (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id    INTEGER NOT NULL,
            bib_number INTEGER NOT NULL,
            name       TEXT NOT NULL,
            age        INTEGER,
            gender     TEXT,
            checked_in INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (race_id) REFERENCES races(id) ON DELETE CASCADE,
            UNIQUE (bib_number)
        );

        -- A runner can only finish once (bib is globally unique).
        CREATE TABLE IF NOT EXISTS finish_times (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id     INTEGER NOT NULL,
            runner_id   INTEGER,
            bib_number  INTEGER NOT NULL,
            finish_time TEXT NOT NULL,
            notes       TEXT,
            logged_at   TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (race_id)  REFERENCES races(id) ON DELETE CASCADE,
            FOREIGN KEY (runner_id) REFERENCES runners(id) ON DELETE SET NULL,
            UNIQUE (bib_number)
        );
    """)
    conn.commit()
    conn.close()
