"""Tests de src.db.models — schema SQLite et migrations."""

import sqlite3

from src.db import models


class TestGetConnection:
    def test_creates_parent_dir(self, tmp_path):
        nested = tmp_path / "a" / "b" / "news.db"
        conn = models.get_connection(nested)
        try:
            assert nested.parent.exists()
        finally:
            conn.close()

    def test_row_factory_is_sqlite_row(self, tmp_path):
        conn = models.get_connection(tmp_path / "x.db")
        try:
            assert conn.row_factory is sqlite3.Row
        finally:
            conn.close()

    def test_foreign_keys_enabled(self, tmp_path):
        conn = models.get_connection(tmp_path / "x.db")
        try:
            (fk_on,) = conn.execute("PRAGMA foreign_keys").fetchone()
            assert fk_on == 1
        finally:
            conn.close()


class TestInitDb:
    def test_creates_expected_tables(self, tmp_path):
        db_path = tmp_path / "news.db"
        models.init_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert {"runs", "articles"}.issubset(tables)
        finally:
            conn.close()

    def test_articles_has_all_scoring_columns(self, tmp_path):
        db_path = tmp_path / "news.db"
        models.init_db(db_path)
        conn = sqlite3.connect(db_path)
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
            for expected in (
                "relevance",
                "relevance_rationale",
                "age_days",
                "freshness_factor",
                "source_factor",
                "community_factor",
                "hn_points",
                "hn_comments",
                "final_score",
            ):
                assert expected in cols
        finally:
            conn.close()

    def test_idempotent_call_does_not_raise(self, tmp_path):
        db_path = tmp_path / "news.db"
        models.init_db(db_path)
        models.init_db(db_path)  # deuxieme appel : ne doit pas lever

    def test_migration_preserves_existing_data(self, tmp_path):
        """Simule une base pre-migration (sans les colonnes de scoring) et verifie
        que init_db les ajoute sans perdre les lignes existantes."""
        db_path = tmp_path / "legacy.db"
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE runs (run_date TEXT PRIMARY KEY, status TEXT NOT NULL,
                started_at TEXT, finished_at TEXT, error TEXT);
            CREATE TABLE articles (id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT NOT NULL, url TEXT NOT NULL, normalized_url TEXT NOT NULL,
                title TEXT NOT NULL, summary TEXT NOT NULL, why_it_matters TEXT,
                source TEXT, published_date TEXT, tags_json TEXT, topic_cluster TEXT,
                links_json TEXT, is_update_of INTEGER, rank INTEGER);
            """
        )
        conn.execute(
            "INSERT INTO runs (run_date, status) VALUES ('2026-01-01', 'done')"
        )
        conn.execute(
            "INSERT INTO articles (run_date, url, normalized_url, title, summary) "
            "VALUES ('2026-01-01', 'https://x.com', 'https://x.com', 'T', 'S')"
        )
        conn.commit()
        conn.close()

        models.init_db(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM articles").fetchone()
            assert row["title"] == "T"
            assert "relevance" in row.keys()
            assert row["relevance"] is None
        finally:
            conn.close()
