"""Node search : lance les requetes sur Exa + Brave et agrege les candidats bruts."""

import asyncio
import logging
from datetime import date, timedelta
from typing import Any, Dict, List

from src.agents.mcp_tools import search_brave, search_exa
from src.agents.state import DigestState
from src.config.settings import settings

logger = logging.getLogger(__name__)

# On ne demande pas trop de resultats par requete pour limiter le bruit/latence.
_RESULTS_PER_QUERY = 6


async def _search_all(
    queries: List[str], start_published_date: str
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Execute toutes les requetes sur les deux providers, en concurrence."""
    tasks = []
    for q in queries:
        tasks.append(
            search_exa(
                q,
                num_results=_RESULTS_PER_QUERY,
                start_published_date=start_published_date,
            )
        )
        tasks.append(search_brave(q, count=_RESULTS_PER_QUERY))

    candidates: List[Dict[str, Any]] = []
    errors: List[str] = []
    for articles, errs in await asyncio.gather(*tasks):
        candidates.extend(articles)
        errors.extend(errs)
    return candidates, errors


def search(state: DigestState) -> DigestState:
    """Node synchrone (wrappe l'async) : recherche Exa + Brave sur toutes les requetes."""
    queries = state.get("queries", [])
    if not queries:
        return {"raw_candidates": [], "errors": ["search: aucune requete"]}

    # Contrainte de fraicheur envoyee a Exa (filtrage a la source).
    reference = date.fromisoformat(state["run_date"])
    since = (reference - timedelta(days=settings.search_window_days)).isoformat()
    logger.info("search: articles publies depuis %s", since)

    candidates, errors = asyncio.run(_search_all(queries, since))

    # Garde uniquement les candidats ayant une URL exploitable.
    candidates = [c for c in candidates if c.get("url")]
    logger.info("search: %d candidats bruts, %d erreurs", len(candidates), len(errors))

    return {
        "raw_candidates": candidates,
        "errors": state.get("errors", []) + errors,
    }
