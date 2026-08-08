"""Node summarize : resume chaque candidat via le LLM (sortie structuree)."""

import asyncio
import logging
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from src.agents.state import ArticleSummary, DigestState
from src.config.llm_config import get_llm, load_prompt
from src.config.settings import settings

logger = logging.getLogger(__name__)

_USER_TEMPLATE = """Analyse l'article suivant.

TITRE: {title}
SOURCE: {source}
DATE: {published_date}
URL: {url}

CONTENU (extrait):
{snippet}
"""


def _cap() -> int:
    # On resume un peu plus que le quota final pour laisser le choix au tri.
    return max(settings.max_articles_per_day * 3, 9)


async def _summarize_all(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    system_prompt = load_prompt("summary_system_prompt.md")
    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", _USER_TEMPLATE)]
    )
    chain = prompt | get_llm().with_structured_output(ArticleSummary)

    async def one(cand: Dict[str, Any]) -> Dict[str, Any]:
        try:
            res: ArticleSummary = await chain.ainvoke(
                {
                    "title": cand.get("title", ""),
                    "source": cand.get("source", ""),
                    "published_date": cand.get("published_date", ""),
                    "url": cand.get("url", ""),
                    "snippet": cand.get("snippet", "") or "(pas d'extrait disponible)",
                }
            )
            return {
                **cand,
                "summary": res.summary,
                "why_it_matters": res.why_it_matters,
                "tags": res.tags,
                "topic_cluster": res.topic_cluster,
                "relevance": res.relevance,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("summarize KO pour %s: %s", cand.get("url"), exc)
            return None

    results = await asyncio.gather(*[one(c) for c in candidates])
    return [r for r in results if r]


def summarize(state: DigestState) -> DigestState:
    candidates = state.get("deduped", [])[: _cap()]
    if not candidates:
        return {"summarized": []}
    summarized = asyncio.run(_summarize_all(candidates))
    logger.info("summarize: %d articles resumes", len(summarized))
    return {"summarized": summarized}
