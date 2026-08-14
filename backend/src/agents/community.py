"""Signal communautaire : reception d'un article sur Hacker News.

Ni Exa ni Brave ne fournissent d'indicateur de qualite. Hacker News offre en
revanche une evaluation par les pairs (points + commentaires) exploitable via
l'API publique Algolia, sans cle d'API.

Principe : l'absence de signal ne penalise jamais (facteur neutre 1.0) — beaucoup
de bons articles ne sont simplement pas postes sur HN. Seule une reception
positive apporte un bonus, plafonne pour eviter qu'un buzz n'ecrase la pertinence.
"""

import asyncio
import logging
import math
from typing import Any, Dict, List, Optional

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)

_HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
_MAX_BONUS = 0.20
_BONUS_PER_DECADE = 0.05


def community_factor(points: Optional[int]) -> float:
    """Facteur multiplicatif dans [1.0, 1.20] derive des points Hacker News.

    Echelle logarithmique : ~10 pts -> 1.05, ~100 -> 1.10, ~1000 -> 1.15.
    Aucun signal (None ou 0) -> 1.0 (neutre, jamais penalisant).
    """
    if not points or points <= 0:
        return 1.0
    bonus = min(_MAX_BONUS, _BONUS_PER_DECADE * math.log10(1 + points))
    return round(1.0 + bonus, 3)


async def _fetch_one(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, int]]:
    """Cherche une story HN pointant sur cette URL exacte."""
    try:
        resp = await client.get(
            _HN_SEARCH_URL,
            params={
                "query": url,
                "restrictSearchableAttributes": "url",
                "tags": "story",
                "hitsPerPage": 3,
            },
        )
        resp.raise_for_status()
        hits = resp.json().get("hits") or []
    except Exception as exc:  # noqa: BLE001 — signal optionnel, jamais bloquant
        logger.debug("HN indisponible pour %s: %s", url, exc)
        return None

    if not hits:
        return None
    # Une meme URL peut etre postee plusieurs fois : on garde la meilleure reception.
    best = max(hits, key=lambda h: h.get("points") or 0)
    return {
        "points": int(best.get("points") or 0),
        "comments": int(best.get("num_comments") or 0),
    }


async def _enrich_all(articles: List[Dict[str, Any]]) -> None:
    async with httpx.AsyncClient(timeout=settings.hn_timeout) as client:
        results = await asyncio.gather(
            *[_fetch_one(client, a.get("url", "")) for a in articles]
        )
    for article, signal in zip(articles, results):
        points = signal["points"] if signal else None
        article["hn_points"] = points
        article["hn_comments"] = signal["comments"] if signal else None
        article["community_factor"] = community_factor(points)


def enrich_with_community(articles: List[Dict[str, Any]]) -> None:
    """Annote les articles avec leur reception HN (mutation en place)."""
    if not articles or not settings.enable_hn_signal:
        for article in articles:
            article.setdefault("community_factor", 1.0)
        return
    try:
        asyncio.run(_enrich_all(articles))
    except Exception as exc:  # noqa: BLE001
        logger.warning("signal communautaire indisponible: %s", exc)
        for article in articles:
            article.setdefault("community_factor", 1.0)
