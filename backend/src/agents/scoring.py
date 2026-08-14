"""Calcul du score de selection : pertinence LLM ponderee par fraicheur et source.

Le LLM fournit une pertinence brute (0-100). Ce module la corrige par deux
facteurs objectifs :
  - la **fraicheur** : un article de veille perd tout interet en vieillissant ;
  - l'**autorite de la source** : editeurs et blogs d'ingenierie de reference
    sont priorises face aux agregateurs / contenus SEO.

    score_final = relevance x facteur_fraicheur x facteur_source
"""

import functools
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import yaml

from src.config.settings import settings

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------- dates

# Formats relatifs renvoyes par certaines sources (Brave) : "3 days ago".
_REL_AGE_RE = re.compile(r"(\d+)\s*(minute|hour|day|week|month|year)s?\s+ago", re.I)
_REL_UNIT_DAYS = {
    "minute": 0,
    "hour": 0,
    "day": 1,
    "week": 7,
    "month": 30,
    "year": 365,
}
_ISO_PREFIX_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def parse_published(value: Any, today: Optional[date] = None) -> Optional[date]:
    """Parse une date de publication heterogene.

    Gere l'ISO 8601 (avec ou sans 'Z'/heure), 'YYYY-MM-DD' et les formats
    relatifs ('3 days ago'). Retourne None si la date est absente ou illisible.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text or text.upper() in ("N/A", "NONE", "NULL", "-"):
        return None

    m = _REL_AGE_RE.search(text)
    if m:
        days = int(m.group(1)) * _REL_UNIT_DAYS[m.group(2).lower()]
        return (today or date.today()) - timedelta(days=days)

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    m = _ISO_PREFIX_RE.match(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def age_in_days(value: Any, reference: date) -> Optional[int]:
    """Age de l'article en jours a la date de reference (None si date inconnue).

    Une date future (horloge/fuseau) est ramenee a 0.
    """
    published = parse_published(value, today=reference)
    if published is None:
        return None
    return max((reference - published).days, 0)


# ---------------------------------------------------------------- fraicheur

def freshness_factor(age_days: Optional[int], window_days: int) -> float:
    """Decote d'anciennete, dans ]0, 1].

    - 0-1 jour            -> 1.0  (actualite chaude)
    - jusqu'a la fenetre  -> decroissance lineaire 1.0 -> 0.6
    - au-dela             -> chute rapide, plancher 0.25
    - date inconnue       -> facteur neutre-bas (configurable)
    """
    if age_days is None:
        return settings.undated_freshness_factor
    if age_days <= 1:
        return 1.0
    if age_days <= window_days:
        span = max(window_days - 1, 1)
        return 1.0 - 0.4 * (age_days - 1) / span
    return max(0.25, 0.6 - 0.05 * (age_days - window_days))


# ------------------------------------------------------------------- source

@functools.lru_cache(maxsize=1)
def _source_weights() -> Tuple[Dict[str, float], float]:
    """Charge (et met en cache) la table de ponderation des domaines."""
    try:
        data = yaml.safe_load(settings.source_weights_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("source_weights.yaml introuvable, ponderation neutre")
        return {}, 1.0
    if not isinstance(data, dict):
        return {}, 1.0
    weights = {
        str(k).lower().lstrip("."): float(v)
        for k, v in (data.get("weights") or {}).items()
    }
    return weights, float(data.get("default_factor", 1.0))


def source_factor(source: str) -> float:
    """Facteur lie a l'autorite du domaine (match par suffixe).

    'blog.jetbrains.com' herite du poids defini pour 'jetbrains.com'.
    """
    weights, default = _source_weights()
    host = (source or "").lower().strip()
    if not host:
        return default
    if host.startswith("www."):
        host = host[4:]
    if host in weights:
        return weights[host]
    for domain, factor in weights.items():
        if host.endswith("." + domain):
            return factor
    return default


# -------------------------------------------------------------------- score

def compute_score(
    article: Dict[str, Any], reference: date, window_days: int
) -> Dict[str, Any]:
    """Calcule le score final et retourne les composantes (pour auditabilite)."""
    try:
        relevance = int(article.get("relevance") or 0)
    except (TypeError, ValueError):
        relevance = 0

    age = article.get("age_days")
    if age is None:
        age = age_in_days(article.get("published_date"), reference)

    fresh = freshness_factor(age, window_days)
    src = source_factor(article.get("source", ""))

    return {
        "relevance": relevance,
        "age_days": age,
        "freshness_factor": round(fresh, 3),
        "source_factor": round(src, 3),
        "final_score": round(relevance * fresh * src, 2),
    }
