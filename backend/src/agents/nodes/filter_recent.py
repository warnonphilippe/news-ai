"""Node filter_recent : ecarte les articles hors fenetre de fraicheur.

Exa filtre deja a la source (`startPublishedDate`), mais Brave ne le permet pas
et certaines dates ne sont exploitables qu'apres parsing. Ce node applique donc
la fenetre de facon uniforme, puis ordonne le vivier du plus frais au plus
ancien : la troncature ulterieure (node summarize) porte ainsi sur les articles
les plus recents plutot que sur un ordre d'arrivee arbitraire.

Les articles sans date exploitable sont conserves (ils sont penalises plus tard
par le facteur de fraicheur), et un repli evite de vider le digest si la
recherche n'a rien remonte d'assez recent.
"""

import logging
from datetime import date
from typing import Any, Dict, List

from src.agents.scoring import age_in_days
from src.agents.state import DigestState
from src.config.settings import settings

logger = logging.getLogger(__name__)


def _sort_key(article: Dict[str, Any]):
    """Trie du plus frais au plus ancien ; les non dates passent apres les dates."""
    age = article.get("age_days")
    return (age is None, age if age is not None else 0)


def filter_recent(state: DigestState) -> DigestState:
    window = settings.search_window_days
    reference = date.fromisoformat(state["run_date"])

    fresh: List[Dict[str, Any]] = []
    stale: List[Dict[str, Any]] = []

    for cand in state.get("deduped", []):
        age = age_in_days(cand.get("published_date"), reference)
        cand["age_days"] = age
        if age is not None and age > window:
            stale.append(cand)
        else:
            fresh.append(cand)

    fresh.sort(key=_sort_key)

    # Repli : si trop peu d'articles frais, on complete avec les moins anciens
    # pour ne pas presenter un digest vide (ils resteront penalises au scoring).
    if len(fresh) < settings.max_articles_per_day and stale:
        stale.sort(key=_sort_key)
        missing = settings.max_articles_per_day - len(fresh)
        fresh.extend(stale[:missing])
        logger.info(
            "filter_recent: seulement %d articles dans la fenetre de %dj, "
            "complement avec %d articles plus anciens",
            len(fresh) - min(missing, len(stale)),
            window,
            min(missing, len(stale)),
        )

    logger.info(
        "filter_recent: %d candidats -> %d retenus (%d hors fenetre de %dj)",
        len(state.get("deduped", [])),
        len(fresh),
        len(stale),
        window,
    )
    return {"deduped": fresh}
