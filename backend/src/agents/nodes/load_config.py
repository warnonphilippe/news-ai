"""Node load_config : charge tags + historique 14j depuis la DB."""

import logging
from typing import List

from src.agents.state import DigestState
from src.config.settings import settings
from src.db.repository import Repository

logger = logging.getLogger(__name__)


def _load_tags() -> List[str]:
    try:
        lines = settings.tags_file.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [t.strip() for t in lines if t.strip()]


def make_load_config(repo: Repository):
    """Fabrique le node load_config avec le repository injecte."""

    def load_config(state: DigestState) -> DigestState:
        run_date = state["run_date"]
        history = repo.get_recent_history(settings.history_days, before_date=run_date)
        tags = _load_tags()
        logger.info(
            "load_config: %d tags, %d articles d'historique", len(tags), len(history)
        )
        return {"tags": tags, "recent_history": history, "errors": []}

    return load_config


def load_config_custom(state: DigestState) -> DigestState:
    """Node load_config pour la recherche personnalisee.

    Ne charge PAS l'historique (recent_history reste vide) : une recherche
    ad hoc ne doit pas ecarter silencieusement un article pertinent au seul
    motif qu'il a deja ete presente dans un digest quotidien. Effet de bord
    utile : dedupe() et novelty_check() se comportent alors correctement sans
    aucune modification (novelty_check court-circuite deja sur historique vide).
    """
    tags = _load_tags()
    logger.info("load_config_custom: %d tags, pas d'historique charge", len(tags))
    return {"tags": tags, "recent_history": [], "errors": []}
