"""Node build_queries : produit la liste des requetes de recherche du jour."""

import logging
from typing import List

import yaml

from src.agents.state import DigestState
from src.config.settings import settings

logger = logging.getLogger(__name__)


def _load_seed_queries() -> List[str]:
    try:
        data = yaml.safe_load(settings.seed_queries_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    queries: List[str] = []
    if isinstance(data, dict):
        for axis in data.values():
            if isinstance(axis, list):
                queries.extend(str(q) for q in axis)
    return queries


def build_queries(state: DigestState) -> DigestState:
    """Combine les requetes seed (2 axes) et quelques requetes fondees sur les tags."""
    queries = _load_seed_queries()

    # Requete d'actualite generique fondee sur les tags principaux.
    top_tags = state.get("tags", [])[:6]
    if top_tags:
        queries.append(
            "latest news and releases about " + ", ".join(top_tags) + " for developers"
        )

    # Deduplique en preservant l'ordre.
    seen = set()
    unique = [q for q in queries if not (q in seen or seen.add(q))]

    logger.info("build_queries: %d requetes", len(unique))
    return {"queries": unique}
