"""Node select_top : ecarte les doublons et garde les N meilleurs (NEW + UPDATE).

Le classement n'utilise pas la pertinence brute du LLM mais un score pondere :

    score_final = relevance x facteur_fraicheur x facteur_source

Les composantes sont attachees a chaque article afin que la selection reste
auditable apres coup (elles sont persistees en base).
"""

import logging
from datetime import date

from src.agents.scoring import compute_score
from src.agents.state import DigestState
from src.config.settings import settings

logger = logging.getLogger(__name__)


def select_top(state: DigestState) -> DigestState:
    candidates = [
        c
        for c in state.get("summarized", [])
        if c.get("novelty") in ("NEW", "UPDATE")
    ]

    reference = date.fromisoformat(state["run_date"])
    window = settings.search_window_days
    for cand in candidates:
        cand.update(compute_score(cand, reference, window))

    candidates.sort(key=lambda a: a.get("final_score", 0), reverse=True)
    selected = candidates[: settings.max_articles_per_day]

    if selected:
        logger.info(
            "select_top: %d retenus sur %d | scores: %s",
            len(selected),
            len(candidates),
            ", ".join(
                f"{a.get('final_score')}(rel={a.get('relevance')},"
                f"age={a.get('age_days')},src={a.get('source_factor')})"
                for a in selected
            ),
        )
    else:
        logger.info("select_top: aucun article retenu")

    return {"selected": selected}
