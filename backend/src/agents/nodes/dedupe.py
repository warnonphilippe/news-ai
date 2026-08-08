"""Node dedupe : normalise les URLs et retire doublons + articles deja vus (14j)."""

import logging
from typing import Any, Dict, List

from src.agents.search_parse import normalize_url
from src.agents.state import DigestState

logger = logging.getLogger(__name__)


def dedupe(state: DigestState) -> DigestState:
    known_urls = {
        h.get("normalized_url", "") for h in state.get("recent_history", [])
    }
    seen: set = set()
    deduped: List[Dict[str, Any]] = []

    for cand in state.get("raw_candidates", []):
        norm = normalize_url(cand.get("url", ""))
        if not norm:
            continue
        cand["normalized_url"] = norm
        if norm in known_urls:
            continue  # deja presente dans les 14 derniers jours
        if norm in seen:
            # Doublon inter-providers : on garde le meilleur snippet.
            existing = next(d for d in deduped if d["normalized_url"] == norm)
            if len(cand.get("snippet", "")) > len(existing.get("snippet", "")):
                existing["snippet"] = cand["snippet"]
            continue
        seen.add(norm)
        deduped.append(cand)

    logger.info(
        "dedupe: %d -> %d candidats uniques et nouveaux",
        len(state.get("raw_candidates", [])),
        len(deduped),
    )
    return {"deduped": deduped}
