"""Node novelty_check : un appel LLM classe chaque candidat NEW / DUPLICATE / UPDATE."""

import logging
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from src.agents.state import DigestState, NoveltyReport
from src.config.llm_config import get_llm, load_prompt

logger = logging.getLogger(__name__)

_USER_TEMPLATE = """HISTORIQUE (articles deja presentes ces 14 derniers jours):
{history}

CANDIDATS DU JOUR:
{candidates}

Emets un verdict pour CHAQUE candidat (identifie par son url).
"""


def _format_history(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "(aucun article dans l'historique)"
    lines = []
    for h in history:
        lines.append(
            f"- id={h['id']} | {h['run_date']} | [{h.get('topic_cluster', '')}] "
            f"{h['title']} :: {h.get('summary', '')[:160]}"
        )
    return "\n".join(lines)


def _format_candidates(candidates: List[Dict[str, Any]]) -> str:
    lines = []
    for c in candidates:
        lines.append(
            f"- url={c['url']} | [{c.get('topic_cluster', '')}] "
            f"{c['title']} :: {c.get('summary', '')[:160]}"
        )
    return "\n".join(lines)


def novelty_check(state: DigestState) -> DigestState:
    candidates = state.get("summarized", [])
    history = state.get("recent_history", [])

    if not candidates:
        return {"summarized": []}

    # Sans historique, tout est nouveau : on evite un appel LLM inutile.
    if not history:
        for c in candidates:
            c["novelty"] = "NEW"
            c["is_update_of"] = None
        return {"summarized": candidates}

    system_prompt = load_prompt("novelty_prompt.md")
    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", _USER_TEMPLATE)]
    )
    chain = prompt | get_llm().with_structured_output(NoveltyReport)

    verdicts: Dict[str, Any] = {}
    try:
        report: NoveltyReport = chain.invoke(
            {
                "history": _format_history(history),
                "candidates": _format_candidates(candidates),
            }
        )
        for v in report.verdicts:
            verdicts[v.url] = v
    except Exception as exc:  # noqa: BLE001 — en cas d'echec, on garde tout en NEW
        logger.warning("novelty_check KO, fallback NEW: %s", exc)

    valid_ids = {h["id"] for h in history}
    for c in candidates:
        v = verdicts.get(c["url"])
        if v is None:
            c["novelty"] = "NEW"
            c["is_update_of"] = None
        else:
            c["novelty"] = v.verdict
            # On ne conserve is_update_of que s'il pointe vers un id historique valide.
            c["is_update_of"] = (
                v.is_update_of
                if (v.verdict == "UPDATE" and v.is_update_of in valid_ids)
                else None
            )

    kept = [c for c in candidates if c["novelty"] in ("NEW", "UPDATE")]
    logger.info(
        "novelty_check: %d candidats -> %d conserves (%d doublons ecartes)",
        len(candidates),
        len(kept),
        len(candidates) - len(kept),
    )
    return {"summarized": candidates}
