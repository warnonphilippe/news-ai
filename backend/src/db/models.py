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
    relevance        INTEGER,               -- pertinence brute LLM (0-100)
    age_days         INTEGER,               -- age au moment du run
    freshness_factor REAL,                  -- decote d'anciennete appliquee
    source_factor    REAL,                  -- ponderation du domaine
    final_score      REAL,                  -- relevance x fraicheur x source
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


# Colonnes ajoutees apres la creation initiale du schema. Appliquees en
# ALTER TABLE sur les bases existantes, pour ne pas perdre l'historique.
_ADDED_COLUMNS = [
    ("articles", "relevance", "INTEGER"),
    ("articles", "age_days", "INTEGER"),
    ("articles", "freshness_factor", "REAL"),
    ("articles", "source_factor", "REAL"),
    ("articles", "final_score", "REAL"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    """Ajoute les colonnes manquantes (idempotent)."""
    for table, column, ctype in _ADDED_COLUMNS:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ctype}")


def init_db(db_path: Path) -> None:
    """Cree les tables si elles n'existent pas, puis applique les migrations."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()
