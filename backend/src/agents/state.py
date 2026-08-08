"""Etat partage du pipeline LangGraph et modeles de sortie structuree."""

from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field


class DigestState(TypedDict, total=False):
    """Etat transporte entre les nodes du graphe."""

    run_date: str
    tags: List[str]
    queries: List[str]
    raw_candidates: List[Dict[str, Any]]      # sortie brute des recherches
    deduped: List[Dict[str, Any]]             # apres dedup URL
    summarized: List[Dict[str, Any]]          # + resume LLM
    recent_history: List[Dict[str, Any]]      # 14 derniers jours (compact)
    selected: List[Dict[str, Any]]            # <= max_articles_per_day
    errors: List[str]


# ---------------------------------------------------------------- summarize

class ArticleSummary(BaseModel):
    """Sortie structuree du LLM pour un article."""

    summary: str = Field(description="Resume factuel de 3 a 5 phrases, en francais.")
    why_it_matters: str = Field(
        description="Pourquoi c'est important pour un dev/architecte Java ou Python (1-2 phrases)."
    )
    tags: List[str] = Field(
        default_factory=list, description="3 a 6 tags techniques pertinents."
    )
    topic_cluster: str = Field(
        description="Etiquette courte du sujet (ex: 'Claude Code', 'RAG', 'LangGraph')."
    )
    relevance: int = Field(
        description="Pertinence 0-100 pour l'audience 'IA for DEV' Java/Python.",
        ge=0,
        le=100,
    )


# ------------------------------------------------------------ novelty check

class NoveltyVerdict(BaseModel):
    url: str = Field(description="URL du candidat evalue.")
    verdict: Literal["NEW", "DUPLICATE", "UPDATE"]
    is_update_of: Optional[int] = Field(
        default=None,
        description="Si verdict=UPDATE : id de l'article historique complete, sinon null.",
    )


class NoveltyReport(BaseModel):
    verdicts: List[NoveltyVerdict]
