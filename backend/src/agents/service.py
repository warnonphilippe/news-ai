"""Service d'orchestration d'un run quotidien (verrou + pipeline + statut)."""

import logging
from typing import Any, Dict, List

from src.agents.graph import build_custom_graph, run_digest
from src.agents.state import DigestState
from src.config.settings import settings
from src.db.repository import Repository, today_str

logger = logging.getLogger(__name__)


def run_daily_digest(repo: Repository, force: bool = False) -> dict:
    """Lance le digest du jour si pas deja fait.

    - Verrou atomique via runs.run_date.
    - force=True supprime le run existant et relance.
    Retourne un statut : {'run_date', 'status', 'started'|'skipped'|'error'}.
    """
    run_date = today_str()

    if force:
        repo.reset_run(run_date)

    started = repo.try_start_run(run_date)
    if not started:
        existing = repo.get_run(run_date)
        status = existing["status"] if existing else "unknown"
        logger.info("run %s deja present (status=%s), skip", run_date, status)
        return {"run_date": run_date, "status": status, "action": "skipped"}

    try:
        logger.info("Demarrage du digest %s", run_date)
        run_digest(repo, run_date)
        repo.finish_run(run_date, status="done")
        logger.info("Digest %s termine", run_date)
        return {"run_date": run_date, "status": "done", "action": "started"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Echec du digest %s", run_date)
        repo.finish_run(run_date, status="error", error=str(exc))
        return {
            "run_date": run_date,
            "status": "error",
            "action": "error",
            "error": str(exc),
        }


def run_custom_search(repo: Repository, query: str) -> List[Dict[str, Any]]:
    """Execute une recherche personnalisee ponctuelle et retourne les articles.

    Contrairement a run_daily_digest : pas de verrou (`try_start_run`/
    `finish_run` — pas de notion de run pour une recherche ad hoc), et le
    resultat n'est PAS persiste (build_custom_graph n'a pas de node persist).
    Chaque appel est independant, meme phrase ou non.
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("le critere de recherche ne peut pas etre vide")

    logger.info("Recherche personnalisee : %r", query)
    graph = build_custom_graph(repo)
    initial: DigestState = {
        "run_date": today_str(),
        "custom_query": query,
        "search_window_days": settings.custom_search_window_days,
        "max_articles": settings.custom_search_max_results,
    }
    final_state = graph.invoke(initial)
    selected = final_state.get("selected", [])

    for rank, art in enumerate(selected, start=1):
        art["rank"] = rank
        art.setdefault("is_update_of", None)
        art.setdefault("links", [])

    logger.info("Recherche personnalisee terminee : %d resultats", len(selected))
    return selected
