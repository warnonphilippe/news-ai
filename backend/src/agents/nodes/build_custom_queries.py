"""Node build_custom_queries : requetes pour la recherche personnalisee.

Contrairement a build_queries.py (2 axes seed fixes), ici la phrase libre de
l'utilisateur EST la requete principale. On ajoute une seule variante legerement
scopee developpeur pour aider les moteurs a rester dans le registre technique,
sans diluer la specificite du critere avec les tags generiques du digest
quotidien.
"""

import logging

from src.agents.state import DigestState

logger = logging.getLogger(__name__)


def build_custom_queries(state: DigestState) -> DigestState:
    query = (state.get("custom_query") or "").strip()
    if not query:
        return {"queries": []}

    queries = [query, f"{query} for software developers"]

    logger.info("build_custom_queries: %d requetes pour %r", len(queries), query)
    return {"queries": queries}
