"""Construction du graphe LangGraph du digest quotidien.

Pipeline lineaire :
    load_config -> build_queries -> search -> dedupe
                -> summarize -> novelty_check -> select_top -> persist
"""

import logging

from langgraph.graph import END, START, StateGraph

from src.agents.nodes.build_queries import build_queries
from src.agents.nodes.dedupe import dedupe
from src.agents.nodes.load_config import make_load_config
from src.agents.nodes.novelty_check import novelty_check
from src.agents.nodes.persist import make_persist
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
    g.add_node("summarize", summarize)
    g.add_node("novelty_check", novelty_check)
    g.add_node("select_top", select_top)
    g.add_node("persist", make_persist(repo))

    g.add_edge(START, "load_config")
    g.add_edge("load_config", "build_queries")
    g.add_edge("build_queries", "search")
    g.add_edge("search", "dedupe")
    g.add_edge("dedupe", "summarize")
    g.add_edge("summarize", "novelty_check")
    g.add_edge("novelty_check", "select_top")
    g.add_edge("select_top", "persist")
    g.add_edge("persist", END)

    return g.compile()


def run_digest(repo: Repository, run_date: str) -> DigestState:
    """Execute le pipeline complet pour une date donnee et retourne l'etat final."""
    graph = build_graph(repo)
    initial: DigestState = {"run_date": run_date}
    final_state = graph.invoke(initial)
    return final_state
