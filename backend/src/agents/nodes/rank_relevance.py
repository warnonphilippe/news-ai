"""Node rank_relevance : note la pertinence de TOUS les candidats en un seul appel.

Deux problemes successifs ont faconne ce node :

1. Noter chaque article dans un appel isole produisait des scores non
   comparables : prive de point de reference, le LLM tassait ses notes
   (mesure : 82-95, ecart-type 4.3). D'ou l'appel unique sur tout le lot.

2. Mais noter « les uns par rapport aux autres » rend la note dependante du
   groupe du jour : un meme article valait 87 seul et 55 face a un lot plus
   fort — un score d'aujourd'hui n'etait donc pas comparable a celui d'hier.

Le prompt (relevance_prompt.md) resout le second point par des **ancres fixes** :
le modele situe chaque candidat par rapport a des exemples de reference
invariants, et non par rapport a ses voisins du jour. L'appel reste unique
(coherence du lot, un seul aller-retour), mais la notation vise l'absolu.
"""

import logging
import statistics
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from src.agents.state import DigestState, RelevanceRanking
from src.config.llm_config import get_llm, load_prompt

logger = logging.getLogger(__name__)

_USER_TEMPLATE = """CANDIDATS DU JOUR ({count} articles) :

{candidates}

Note chacun d'eux selon la grille, en les comparant entre eux.
"""

# Note attribuee quand le LLM n'a pas renvoye de verdict pour un candidat :
# volontairement mediocre pour ne pas favoriser un article non evalue.
_FALLBACK_SCORE = 40


def _format_candidates(candidates: List[Dict[str, Any]]) -> str:
    lines = []
    for i, c in enumerate(candidates, start=1):
        lines.append(
            f"{i}. url={c['url']}\n"
            f"   source: {c.get('source', '?')} | sujet: {c.get('topic_cluster', '?')}"
            f" | age: {c.get('age_days', '?')} j\n"
            f"   titre: {c.get('title', '')}\n"
            f"   resume: {(c.get('summary') or '')[:280]}"
        )
    return "\n\n".join(lines)


def rank_relevance(state: DigestState) -> DigestState:
    # Seuls les articles retenus par novelty_check meritent d'etre notes.
    candidates = [
        c
        for c in state.get("summarized", [])
        if c.get("novelty") in ("NEW", "UPDATE")
    ]
    if not candidates:
        return {}

    prompt = ChatPromptTemplate.from_messages(
        [("system", load_prompt("relevance_prompt.md")), ("human", _USER_TEMPLATE)]
    )
    chain = prompt | get_llm().with_structured_output(RelevanceRanking)

    scores: Dict[str, Any] = {}
    try:
        ranking: RelevanceRanking = chain.invoke(
            {
                "count": len(candidates),
                "candidates": _format_candidates(candidates),
            }
        )
        scores = {item.url: item for item in ranking.items}
    except Exception as exc:  # noqa: BLE001 — degradation : on garde un score neutre
        logger.warning("rank_relevance KO, scores neutres appliques: %s", exc)

    for cand in candidates:
        item = scores.get(cand["url"])
        cand["relevance"] = item.score if item else _FALLBACK_SCORE
        cand["relevance_rationale"] = item.rationale if item else ""

    values = [c["relevance"] for c in candidates]
    if len(values) > 1:
        logger.info(
            "rank_relevance: %d notes | min=%d max=%d etendue=%d ecart-type=%.1f",
            len(values),
            min(values),
            max(values),
            max(values) - min(values),
            statistics.pstdev(values),
        )
    return {"summarized": state.get("summarized", [])}
