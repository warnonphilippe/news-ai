"""Tests d'integration du graphe LangGraph (cablage entre nodes deja testes unitairement).

Seules les dependances externes (recherche Exa/Brave, appels LLM, API Hacker
News) sont mockees ; le reste du pipeline (dedup, filtre de fraicheur, scoring,
selection) tourne pour de vrai a travers le graphe compile, pour verifier le
cablage reel plutot que de re-tester chaque node isolement.
"""

import pytest

from src.agents import graph as graph_module
from src.agents.state import (
    ArticleSummary,
    NoveltyReport,
    RelevanceRanking,
)
from tests.conftest import FakeStructuredLLM


@pytest.fixture
def patch_pipeline_externals(monkeypatch):
    """Mocke recherche + LLM + communaute pour tout le pipeline, sans reseau."""
    from src.agents.nodes import (
        community_signal as community_node,
        novelty_check as novelty_node,
        rank_relevance as rank_node,
        rank_relevance_custom as rank_custom_node,
        search as search_node,
        summarize as summarize_node,
    )

    async def _fake_exa(query, num_results, start_published_date):
        return [
            {
                "url": f"https://exa.example/{query}",
                "title": f"Exa: {query}",
                "snippet": "extrait exa",
                "source": "exa.example",
                "published_date": "2026-08-13",
                "provider": "exa",
            }
        ], []

    async def _fake_brave(query, count):
        return [
            {
                "url": f"https://brave.example/{query}",
                "title": f"Brave: {query}",
                "snippet": "extrait brave",
                "source": "brave.example",
                "published_date": "2026-08-12",
                "provider": "brave",
            }
        ], []

    monkeypatch.setattr(search_node, "search_exa", _fake_exa)
    monkeypatch.setattr(search_node, "search_brave", _fake_brave)

    monkeypatch.setattr(
        summarize_node,
        "get_llm",
        lambda *a, **kw: FakeStructuredLLM(
            lambda pv: ArticleSummary(
                summary="Resume genere pour le test.",
                why_it_matters="Impact pour le test.",
                tags=["Test"],
                topic_cluster="Test",
            )
        ),
    )
    monkeypatch.setattr(
        novelty_node, "get_llm", lambda *a, **kw: FakeStructuredLLM(lambda pv: NoveltyReport(verdicts=[]))
    )
    monkeypatch.setattr(
        rank_node,
        "get_llm",
        lambda *a, **kw: FakeStructuredLLM(lambda pv: RelevanceRanking(items=[])),
    )
    monkeypatch.setattr(
        rank_custom_node,
        "get_llm",
        lambda *a, **kw: FakeStructuredLLM(lambda pv: RelevanceRanking(items=[])),
    )
    monkeypatch.setattr(community_node, "enrich_with_community", lambda articles: None)


class TestGraphStructure:
    def test_build_graph_has_expected_nodes_and_persist(self, repo):
        g = graph_module.build_graph(repo)
        nodes = {n for n in g.get_graph().nodes if not n.startswith("__")}
        assert nodes == {
            "load_config",
            "build_queries",
            "search",
            "dedupe",
            "filter_recent",
            "summarize",
            "novelty_check",
            "rank_relevance",
            "community_signal",
            "select_top",
            "persist",
        }

    def test_build_custom_graph_has_no_persist_node(self, repo):
        g = graph_module.build_custom_graph(repo)
        nodes = {n for n in g.get_graph().nodes if not n.startswith("__")}
        assert "persist" not in nodes
        assert nodes == {
            "load_config",
            "build_queries",
            "search",
            "dedupe",
            "filter_recent",
            "summarize",
            "novelty_check",
            "rank_relevance",
            "community_signal",
            "select_top",
        }


class TestRunDigestEndToEnd:
    def test_produces_selected_articles_and_persists_them(
        self, repo, isolated_data_dir, patch_pipeline_externals, monkeypatch
    ):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)

        repo.try_start_run("2026-08-14")
        final_state = graph_module.run_digest(repo, "2026-08-14")

        selected = final_state["selected"]
        assert 0 < len(selected) <= 5
        # Chaque article selectionne porte les composantes de score.
        for art in selected:
            assert "final_score" in art
            assert "relevance" in art

        digest = repo.get_digest("2026-08-14")
        assert len(digest) == len(selected)

    def test_novelty_field_present_on_selected_articles(
        self, repo, isolated_data_dir, patch_pipeline_externals
    ):
        repo.try_start_run("2026-08-14")
        final_state = graph_module.run_digest(repo, "2026-08-14")
        assert all(a["novelty"] in ("NEW", "UPDATE") for a in final_state["selected"])

    def test_second_run_excludes_articles_from_first(
        self, repo, isolated_data_dir, patch_pipeline_externals
    ):
        """Verifie le cablage dedupe<->load_config : l'historique du jour 1 doit
        influencer effectivement le jour 2 via le graphe complet."""
        repo.try_start_run("2026-08-10")
        first_state = graph_module.run_digest(repo, "2026-08-10")
        first_urls = {a["url"] for a in first_state["selected"]}
        assert first_urls  # sanity : le premier run a produit des resultats

        repo.try_start_run("2026-08-14")
        second_state = graph_module.run_digest(repo, "2026-08-14")
        second_urls = {a["url"] for a in second_state["selected"]}

        # Les fausses recherches sont deterministes (memes requetes -> memes URLs) :
        # sans le dedup contre l'historique, les 2 runs produiraient les memes URLs.
        assert first_urls.isdisjoint(second_urls)


class TestRunCustomGraphEndToEnd:
    def test_custom_graph_ignores_history_and_uses_custom_ranking(
        self, repo, isolated_data_dir, patch_pipeline_externals
    ):
        from src.agents.state import DigestState

        # Un digest quotidien existant ne doit PAS reduire les resultats de la
        # recherche personnalisee (load_config_custom ne charge pas l'historique).
        repo.try_start_run("2026-08-10")
        graph_module.run_digest(repo, "2026-08-10")

        g = graph_module.build_custom_graph(repo)
        initial: DigestState = {
            "run_date": "2026-08-14",
            "custom_query": "test query",
            "search_window_days": 30,
            "max_articles": 10,
        }
        final_state = g.invoke(initial)

        assert len(final_state["selected"]) > 0
        # Aucune persistance : le graphe custom n'a pas de node persist.
        assert repo.get_digest("2026-08-14") == []

    def test_custom_graph_respects_max_articles_override(
        self, repo, isolated_data_dir, patch_pipeline_externals
    ):
        from src.agents.state import DigestState

        g = graph_module.build_custom_graph(repo)
        initial: DigestState = {
            "run_date": "2026-08-14",
            "custom_query": "test query",
            "search_window_days": 30,
            "max_articles": 1,
        }
        final_state = g.invoke(initial)
        assert len(final_state["selected"]) <= 1
