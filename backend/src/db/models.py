"""Schema SQLite et helpers de connexion.

On utilise sqlite3 de la stdlib pour rester portable et sans dependance externe.
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_date    TEXT PRIMARY KEY,          -- 'YYYY-MM-DD' (heure locale)
    status      TEXT NOT NULL,             -- 'running' | 'done' | 'error'
    started_at  TEXT,
    finished_at TEXT,
    error       TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date       TEXT NOT NULL,
    url            TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    title          TEXT NOT NULL,
    summary        TEXT NOT NULL,
    why_it_matters TEXT,
    source         TEXT,
    published_date TEXT,
    tags_json      TEXT,                    -- JSON array
    topic_cluster  TEXT,
    links_json     TEXT,                    -- JSON array de {title,url}
    is_update_of   INTEGER,                 -- FK articles.id ou NULL
    rank           INTEGER,
    FOREIGN KEY (run_date) REFERENCES runs(run_date),
    FOREIGN KEY (is_update_of) REFERENCES articles(id)
);

CREATE INDEX IF NOT EXISTS idx_articles_norm ON articles(normalized_url);
CREATE INDEX IF NOT EXISTS idx_articles_run  ON articles(run_date);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec row_factory + FK activees."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    """Cree les tables si elles n'existent pas."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
