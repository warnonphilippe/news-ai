"""Node community_signal : annote les candidats avec leur reception Hacker News."""

import logging

from src.agents.community import enrich_with_community
from src.agents.state import DigestState

logger = logging.getLogger(__name__)


def community_signal(state: DigestState) -> DigestState:
    # Uniquement les candidats encore en lice, pour limiter les appels HTTP.
    candidates = [
        c
        for c in state.get("summarized", [])
        if c.get("novelty") in ("NEW", "UPDATE")
    ]
    if not candidates:
        return {}

    enrich_with_community(candidates)

    rated = [c for c in candidates if c.get("hn_points")]
    logger.info(
        "community_signal: %d/%d articles avec signal HN%s",
        len(rated),
        len(candidates),
        (
            " (max " + str(max(c["hn_points"] for c in rated)) + " pts)"
            if rated
            else ""
        ),
    )
    return {"summarized": state.get("summarized", [])}
