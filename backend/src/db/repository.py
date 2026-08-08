"""Acces aux donnees : runs (verrou journalier) et articles (historique / persist)."""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.db.models import get_connection, init_db

logger = logging.getLogger(__name__)


def today_str() -> str:
    """Date du jour au format 'YYYY-MM-DD' en heure locale."""
    return date.today().isoformat()


class Repository:
    """Couche d'acces SQLite. Une connexion courte par operation (thread-safe)."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        init_db(db_path)

    # ----------------------------------------------------------------- runs

    def try_start_run(self, run_date: str) -> bool:
        """Verrou atomique : cree la ligne run 'running' si absente.

        Retourne True si ce process vient de demarrer le run (personne d'autre
        ne l'avait fait), False si un run existe deja pour cette date.
        """
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                "INSERT OR IGNORE INTO runs (run_date, status, started_at) "
                "VALUES (?, 'running', ?)",
                (run_date, datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()
            return cur.rowcount == 1
        finally:
            conn.close()

    def get_run(self, run_date: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_date = ?", (run_date,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def finish_run(self, run_date: str, status: str, error: Optional[str] = None) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "UPDATE runs SET status = ?, finished_at = ?, error = ? "
                "WHERE run_date = ?",
                (status, datetime.now().isoformat(timespec="seconds"), error, run_date),
            )
            conn.commit()
        finally:
            conn.close()

    def reset_run(self, run_date: str) -> None:
        """Supprime un run (et ses articles) — utile pour relancer manuellement."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("DELETE FROM articles WHERE run_date = ?", (run_date,))
            conn.execute("DELETE FROM runs WHERE run_date = ?", (run_date,))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------- articles

    def get_recent_history(self, days: int, before_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Articles presentes dans la fenetre [before_date - days, before_date).

        Sert au node novelty_check et au dedup URL. Retourne une forme compacte.
        """
        anchor = date.fromisoformat(before_date) if before_date else date.today()
        since = (anchor - timedelta(days=days)).isoformat()
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT id, run_date, url, normalized_url, title, summary, "
                "topic_cluster FROM articles "
                "WHERE run_date >= ? AND run_date < ? "
                "ORDER BY run_date DESC, rank ASC",
                (since, anchor.isoformat()),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def known_normalized_urls(self, days: int, before_date: Optional[str] = None) -> set:
        """Ensemble des URLs normalisees deja vues dans la fenetre d'historique."""
        return {h["normalized_url"] for h in self.get_recent_history(days, before_date)}

    def save_articles(self, run_date: str, articles: List[Dict[str, Any]]) -> None:
        """Persiste les articles selectionnes pour un run."""
        conn = get_connection(self.db_path)
        try:
            for rank, art in enumerate(articles, start=1):
                conn.execute(
                    "INSERT INTO articles (run_date, url, normalized_url, title, "
                    "summary, why_it_matters, source, published_date, tags_json, "
                    "topic_cluster, links_json, is_update_of, rank) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_date,
                        art.get("url", ""),
                        art.get("normalized_url", ""),
                        art.get("title", ""),
                        art.get("summary", ""),
                        art.get("why_it_matters", ""),
                        art.get("source", ""),
                        art.get("published_date", ""),
                        json.dumps(art.get("tags", []), ensure_ascii=False),
                        art.get("topic_cluster", ""),
                        json.dumps(art.get("links", []), ensure_ascii=False),
                        art.get("is_update_of"),
                        rank,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def get_digest(self, run_date: str) -> List[Dict[str, Any]]:
        """Articles d'une date donnee, ordonnes par rank."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM articles WHERE run_date = ? ORDER BY rank ASC",
                (run_date,),
            ).fetchall()
            return [self._row_to_article(r) for r in rows]
        finally:
            conn.close()

    def get_history_index(self, days: int) -> List[Dict[str, Any]]:
        """Liste des runs recents avec compteur d'articles (pour la sidebar)."""
        since = (date.today() - timedelta(days=days)).isoformat()
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT r.run_date, r.status, COUNT(a.id) AS count "
                "FROM runs r LEFT JOIN articles a ON a.run_date = r.run_date "
                "WHERE r.run_date >= ? "
                "GROUP BY r.run_date ORDER BY r.run_date DESC",
                (since,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_article(row) -> Dict[str, Any]:
        d = dict(row)
        d["tags"] = json.loads(d.pop("tags_json") or "[]")
        d["links"] = json.loads(d.pop("links_json") or "[]")
        return d
