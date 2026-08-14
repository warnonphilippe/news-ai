"""Tests du node rank_relevance_custom (recherche personnalisee, critere libre)."""

from src.agents.nodes import rank_relevance_custom as rrc
from src.agents.state import RelevanceRanking, RelevanceScore


class TestRankRelevanceCustom:
    def test_no_eligible_candidates_returns_empty_dict(self):
        state = {
            "custom_query": "RAG",
            "summarized": [{"url": "https://a.com", "novelty": "DUPLICATE"}],
        }
        assert rrc.rank_relevance_custom(state) == {}

    def test_missing_query_returns_empty_dict_even_with_candidates(self):
        state = {
            "summarized": [{"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"}]
        }
        assert rrc.rank_relevance_custom(state) == {}

    def test_empty_query_string_returns_empty_dict(self):
        state = {
            "custom_query": "",
            "summarized": [{"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"}],
        }
        assert rrc.rank_relevance_custom(state) == {}

    def test_query_injected_into_prompt(self, patch_llm):
        captured = {}

        def _capture(pv):
            from tests.conftest import prompt_text

            captured["text"] = prompt_text(pv)
            return RelevanceRanking(items=[])

        patch_llm(rrc, _capture)

        state = {
            "custom_query": "RAG avec pgvector",
            "summarized": [
                {"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"}
            ],
        }
        rrc.rank_relevance_custom(state)
        assert "RAG avec pgvector" in captured["text"]

    def test_scores_applied_by_url(self, patch_llm):
        ranking = RelevanceRanking(
            items=[RelevanceScore(url="https://a.com", score=95, rationale="tres cible")]
        )
        patch_llm(rrc, lambda _pv: ranking)

        state = {
            "custom_query": "Kubernetes",
            "summarized": [
                {"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"}
            ],
        }
        result = rrc.rank_relevance_custom(state)
        assert result["summarized"][0]["relevance"] == 95
        assert result["summarized"][0]["relevance_rationale"] == "tres cible"

    def test_fallback_score_differs_from_daily_node(self, patch_llm):
        # rank_relevance_custom utilise un fallback (30) different de rank_relevance (40),
        # deliberement plus severe pour ne pas favoriser un article non evalue.
        patch_llm(rrc, lambda _pv: RelevanceRanking(items=[]))

        state = {
            "custom_query": "Kubernetes",
            "summarized": [
                {"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"}
            ],
        }
        result = rrc.rank_relevance_custom(state)
        assert result["summarized"][0]["relevance"] == 30

    def test_llm_exception_applies_fallback_to_all(self, patch_llm):
        patch_llm(rrc, lambda _pv: RuntimeError("azure indisponible"))

        state = {
            "custom_query": "Kubernetes",
            "summarized": [
                {"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"},
                {"url": "https://b.com", "novelty": "UPDATE", "title": "B", "summary": "s"},
            ],
        }
        result = rrc.rank_relevance_custom(state)
        assert all(c["relevance"] == 30 for c in result["summarized"])
