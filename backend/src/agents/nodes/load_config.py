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
