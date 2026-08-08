"""Service d'orchestration d'un run quotidien (verrou + pipeline + statut)."""

import logging

from src.agents.graph import run_digest
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
