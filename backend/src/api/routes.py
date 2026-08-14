"""Endpoints REST du backend."""

import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.agents.service import run_custom_search, run_daily_digest
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


class CustomSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)


@router.post("/search")
def search_custom(payload: CustomSearchRequest):
    """Recherche personnalisee ponctuelle (critere libre), jamais persistee.

    Execution SYNCHRONE (pas de BackgroundTasks/polling) : app locale
    mono-utilisateur, resultat ephemere donc rien a relire entre deux
    requetes. Route declaree en `def` (pas `async def`) a dessein : les nodes
    reutilises (search, summarize) appellent asyncio.run() en interne, ce qui
    leverait RuntimeError dans un handler deja dans la boucle d'evenements.
    En `def` classique, Starlette dispatch vers un threadpool (meme mecanisme
    que BackgroundTasks.add_task ci-dessus).
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Le critere de recherche est vide")
    try:
        articles = run_custom_search(repo, query)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Recherche personnalisee KO")
        raise HTTPException(status_code=500, detail=f"La recherche a echoue : {exc}")
    return {"query": query, "count": len(articles), "articles": articles}
