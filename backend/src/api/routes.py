"""Endpoints REST du backend."""

import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.agents.service import run_daily_digest
from src.config.settings import settings
from src.db.repository import Repository, today_str

logger = logging.getLogger(__name__)

router = APIRouter()
repo = Repository(settings.db_path)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/digest/today")
def digest_today():
    run_date = today_str()
    run = repo.get_run(run_date)
    return {
        "run_date": run_date,
        "status": run["status"] if run else "none",
        "articles": repo.get_digest(run_date),
    }


@router.get("/digest/{run_date}")
def digest_by_date(run_date: str):
    try:
        date.fromisoformat(run_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de date invalide (YYYY-MM-DD)")
    run = repo.get_run(run_date)
    return {
        "run_date": run_date,
        "status": run["status"] if run else "none",
        "articles": repo.get_digest(run_date),
    }


@router.get("/history")
def history():
    return {"days": repo.get_history_index(settings.history_days)}


@router.post("/run")
def run(background_tasks: BackgroundTasks, force: bool = False):
    """Declenche le digest du jour en tache de fond (idempotent).

    Si un run est deja 'done' pour aujourd'hui, ne relance pas (sauf force=true).
    Retourne immediatement le statut ; le frontend poll ensuite /digest/today.
    """
    run_date = today_str()
    existing = repo.get_run(run_date)

    if existing and existing["status"] == "running":
        return {"run_date": run_date, "status": "running", "action": "already_running"}

    if existing and existing["status"] == "done" and not force:
        return {"run_date": run_date, "status": "done", "action": "skipped"}

    # Lance en tache de fond ; le verrou try_start_run gere la concurrence.
    background_tasks.add_task(run_daily_digest, repo, force)
    return {"run_date": run_date, "status": "running", "action": "started"}
