"""Node persist : ecrit les articles selectionnes dans SQLite."""

import logging

from src.agents.state import DigestState
from src.db.repository import Repository

logger = logging.getLogger(__name__)


def make_persist(repo: Repository):
    """Fabrique le node persist en lui injectant le repository."""

    def persist(state: DigestState) -> DigestState:
        run_date = state["run_date"]
        selected = state.get("selected", [])
        # 'links' : on repart des ressources complementaires si presentes, sinon vide.
        for art in selected:
            art.setdefault("links", art.get("links", []))
        repo.save_articles(run_date, selected)
        logger.info("persist: %d articles ecrits pour %s", len(selected), run_date)
        return {}

    return persist
