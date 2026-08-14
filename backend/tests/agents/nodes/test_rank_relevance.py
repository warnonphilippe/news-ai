"""Tests du node rank_relevance (digest quotidien, ancres fixes)."""

from src.agents.nodes import rank_relevance as rr
from src.agents.state import RelevanceRanking, RelevanceScore


class TestRankRelevance:
    def test_no_eligible_candidates_returns_empty_dict(self):
        state = {"summarized": [{"url": "https://a.com", "novelty": "DUPLICATE"}]}
        assert rr.rank_relevance(state) == {}

    def test_missing_summarized_returns_empty_dict(self):
        assert rr.rank_relevance({}) == {}

    def test_only_new_and_update_are_scored(self, patch_llm):
        captured = {}

        def _capture(pv):
            from tests.conftest import prompt_text

            captured["text"] = prompt_text(pv)
            return RelevanceRanking(items=[])

        patch_llm(rr, _capture)

        state = {
            "summarized": [
                {"url": "https://new.com", "novelty": "NEW", "title": "N", "summary": "s"},
                {"url": "https://dup.com", "novelty": "DUPLICATE", "title": "D", "summary": "s"},
                {"url": "https://upd.com", "novelty": "UPDATE", "title": "U", "summary": "s"},
            ]
        }
        rr.rank_relevance(state)
        assert "https://new.com" in captured["text"]
        assert "https://upd.com" in captured["text"]
        assert "https://dup.com" not in captured["text"]

    def test_scores_applied_by_url(self, patch_llm):
        ranking = RelevanceRanking(
            items=[
                RelevanceScore(url="https://a.com", score=90, rationale="excellent"),
                RelevanceScore(url="https://b.com", score=40, rationale="faible"),
            ]
        )
        patch_llm(rr, lambda _pv: ranking)

        state = {
            "summarized": [
                {"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"},
                {"url": "https://b.com", "novelty": "NEW", "title": "B", "summary": "s"},
            ]
        }
        result = rr.rank_relevance(state)
        by_url = {c["url"]: c for c in result["summarized"]}
        assert by_url["https://a.com"]["relevance"] == 90
        assert by_url["https://a.com"]["relevance_rationale"] == "excellent"
        assert by_url["https://b.com"]["relevance"] == 40

    def test_candidate_missing_from_response_gets_fallback_score(self, patch_llm):
        patch_llm(rr, lambda _pv: RelevanceRanking(items=[]))

        state = {
            "summarized": [
                {"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"},
            ]
        }
        result = rr.rank_relevance(state)
        assert result["summarized"][0]["relevance"] == 40  # _FALLBACK_SCORE
        assert result["summarized"][0]["relevance_rationale"] == ""

    def test_llm_exception_applies_fallback_to_all(self, patch_llm):
        patch_llm(rr, lambda _pv: RuntimeError("azure indisponible"))

        state = {
            "summarized": [
                {"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"},
                {"url": "https://b.com", "novelty": "UPDATE", "title": "B", "summary": "s"},
            ]
        }
        result = rr.rank_relevance(state)
        assert all(c["relevance"] == 40 for c in result["summarized"])

    def test_untouched_duplicate_candidates_remain_in_state_unmodified(self, patch_llm):
        patch_llm(rr, lambda _pv: RelevanceRanking(items=[]))
        dup = {"url": "https://dup.com", "novelty": "DUPLICATE", "title": "D", "summary": "s"}
        state = {
            "summarized": [
                dup,
                {"url": "https://a.com", "novelty": "NEW", "title": "A", "summary": "s"},
            ]
        }
        result = rr.rank_relevance(state)
        by_url = {c["url"]: c for c in result["summarized"]}
        assert "relevance" not in by_url["https://dup.com"]
