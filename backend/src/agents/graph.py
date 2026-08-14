"""Construction du graphe LangGraph du digest quotidien.

Pipeline lineaire :
    load_config -> build_queries -> search -> dedupe -> filter_recent
                -> summarize -> novelty_check -> rank_relevance
                -> community_signal -> select_top -> persist
"""

import logging

from langgraph.graph import END, START, StateGraph

from src.agents.nodes.build_custom_queries import build_custom_queries
from src.agents.nodes.build_queries import build_queries
from src.agents.nodes.dedupe import dedupe
from src.agents.nodes.filter_recent import filter_recent
from src.agents.nodes.load_config import load_config_custom, make_load_config
from src.agents.nodes.novelty_check import novelty_check
from src.agents.nodes.community_signal import community_signal
from src.agents.nodes.persist import make_persist
from src.agents.nodes.rank_relevance import rank_relevance
from src.agents.nodes.rank_relevance_custom import rank_relevance_custom
from src.agents.nodes.search import search
from src.agents.nodes.select import select_top
from src.agents.nodes.summarize import summarize
from src.agents.state import DigestState
from src.db.repository import Repository

logger = logging.getLogger(__name__)


def build_graph(repo: Repository):
    """Assemble et compile le StateGraph du digest."""
    g = StateGraph(DigestState)

    g.add_node("load_config", make_load_config(repo))
    g.add_node("build_queries", build_queries)
    g.add_node("search", search)
    g.add_node("dedupe", dedupe)
    g.add_node("filter_recent", filter_recent)
    g.add_node("summarize", summarize)
    g.add_node("novelty_check", novelty_check)
    g.add_node("rank_relevance", rank_relevance)
    g.add_node("community_signal", community_signal)
    g.add_node("select_top", select_top)
    g.add_node("persist", make_persist(repo))

    g.add_edge(START, "load_config")
    g.add_edge("load_config", "build_queries")
    g.add_edge("build_queries", "search")
    g.add_edge("search", "dedupe")
    g.add_edge("dedupe", "filter_recent")
    g.add_edge("filter_recent", "summarize")
    g.add_edge("summarize", "novelty_check")
    g.add_edge("novelty_check", "rank_relevance")
    g.add_edge("rank_relevance", "community_signal")
    g.add_edge("community_signal", "select_top")
    g.add_edge("select_top", "persist")
    g.add_edge("persist", END)

    return g.compile()


def run_digest(repo: Repository, run_date: str) -> DigestState:
    """Execute le pipeline complet pour une date donnee et retourne l'etat final."""
    graph = build_graph(repo)
    initial: DigestState = {"run_date": run_date}
    final_state = graph.invoke(initial)
    return final_state


def build_custom_graph(repo: Repository):
    """Assemble et compile le StateGraph de la recherche personnalisee.

    Graphe distinct de build_graph (au lieu de branchements conditionnels dans
    des nodes partages) pour que le pipeline quotidien reste a zero diff : la
    non-regression est ainsi garantie par construction, pas seulement testee
    a l'oeil. Reutilise 7 des 9 nodes du digest quotidien tels quels ; seuls
    build_queries, load_config et rank_relevance different, et il n'y a pas de
    node persist (rien n'est ecrit en base pour une recherche ad hoc).
    """
    g = StateGraph(DigestState)

    g.add_node("load_config", load_config_custom)
    g.add_node("build_queries", build_custom_queries)
    g.add_node("search", search)
    g.add_node("dedupe", dedupe)
    g.add_node("filter_recent", filter_recent)
    g.add_node("summarize", summarize)
    g.add_node("novelty_check", novelty_check)
    g.add_node("rank_relevance", rank_relevance_custom)
    g.add_node("community_signal", community_signal)
    g.add_node("select_top", select_top)

    g.add_edge(START, "load_config")
    g.add_edge("load_config", "build_queries")
    g.add_edge("build_queries", "search")
    g.add_edge("search", "dedupe")
    g.add_edge("dedupe", "filter_recent")
    g.add_edge("filter_recent", "summarize")
    g.add_edge("summarize", "novelty_check")
    g.add_edge("novelty_check", "rank_relevance")
    g.add_edge("rank_relevance", "community_signal")
    g.add_edge("community_signal", "select_top")
    g.add_edge("select_top", END)

    return g.compile()
