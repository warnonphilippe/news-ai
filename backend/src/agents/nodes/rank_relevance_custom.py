"""Node rank_relevance_custom : note la pertinence par rapport a un critere libre.

Independant de rank_relevance.py (digest quotidien) plutot que factorise avec
lui : ce dernier reste a zero diff, ce qui garantit structurellement l'absence
de regression sur le pipeline quotidien. Meme mecanique generale (un seul appel
LLM sur tout le lot, sortie structuree RelevanceRanking), mais grille et prompt
dedies ou la correspondance au critere de recherche est l'axe dominant
(cf. assets/custom_relevance_prompt.md), avec un garde-fou de perimetre pour
rester dans le theme IA-for-DEV.
"""

import logging
import statistics
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from src.agents.state import DigestState, RelevanceRanking
from src.config.llm_config import get_llm, load_prompt

logger = logging.getLogger(__name__)

_USER_TEMPLATE = """CRITERE DE RECHERCHE (formule par l'utilisateur) : {query}

CANDIDATS ({count} articles) :

{candidates}

Note chacun d'eux selon sa correspondance au critere ci-dessus.
"""

# Note de repli si le LLM omet un candidat : mediocre, sans favoriser l'oubli.
_FALLBACK_SCORE = 30


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


def rank_relevance_custom(state: DigestState) -> DigestState:
    candidates = [
        c
        for c in state.get("summarized", [])
        if c.get("novelty") in ("NEW", "UPDATE")
    ]
    query = state.get("custom_query") or ""
    if not candidates or not query:
        return {}

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt("custom_relevance_prompt.md")),
            ("human", _USER_TEMPLATE),
        ]
    )
    chain = prompt | get_llm().with_structured_output(RelevanceRanking)

    scores: Dict[str, Any] = {}
    try:
        ranking: RelevanceRanking = chain.invoke(
            {
                "query": query,
                "count": len(candidates),
                "candidates": _format_candidates(candidates),
            }
        )
        scores = {item.url: item for item in ranking.items}
    except Exception as exc:  # noqa: BLE001 — degradation : score de repli
        logger.warning("rank_relevance_custom KO, scores de repli appliques: %s", exc)

    for cand in candidates:
        item = scores.get(cand["url"])
        cand["relevance"] = item.score if item else _FALLBACK_SCORE
        cand["relevance_rationale"] = item.rationale if item else ""

    values = [c["relevance"] for c in candidates]
    if len(values) > 1:
        logger.info(
            "rank_relevance_custom: %d notes pour %r | min=%d max=%d ecart-type=%.1f",
            len(values),
            query,
            min(values),
            max(values),
            statistics.pstdev(values),
        )
    return {"summarized": state.get("summarized", [])}
