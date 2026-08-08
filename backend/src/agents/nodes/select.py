"""Node select_top5 : ecarte les doublons et garde les N meilleurs (NEW + UPDATE)."""

import logging
from typing import Any, Dict, List

from src.agents.state import DigestState
from src.config.settings import settings

logger = logging.getLogger(__name__)


def _relevance(article: Dict[str, Any]) -> int:
    try:
        return int(article.get("relevance") or 0)
    except (TypeError, ValueError):
        return 0


def select_top(state: DigestState) -> DigestState:
    candidates = [
        c
        for c in state.get("summarized", [])
        if c.get("novelty") in ("NEW", "UPDATE")
    ]
    # Tri principal : pertinence decroissante, puis date de publication recente.
    candidates.sort(
        key=lambda a: (_relevance(a), a.get("published_date", "")),
        reverse=True,
    )

    selected = candidates[: settings.max_articles_per_day]
    logger.info("select_top: %d articles retenus", len(selected))
    return {"selected": selected}
