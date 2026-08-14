"""Tests du node community_signal."""

from src.agents.nodes import community_signal as cs


class TestCommunitySignal:
    def test_no_eligible_candidates_returns_empty_dict(self):
        state = {"summarized": [{"url": "https://a.com", "novelty": "DUPLICATE"}]}
        assert cs.community_signal(state) == {}

    def test_missing_summarized_returns_empty_dict(self):
        assert cs.community_signal({}) == {}

    def test_calls_enrich_with_only_eligible_candidates(self, monkeypatch):
        received = {}

        def _fake_enrich(articles):
            received["articles"] = list(articles)
            for a in articles:
                a["community_factor"] = 1.0

        monkeypatch.setattr(cs, "enrich_with_community", _fake_enrich)

        state = {
            "summarized": [
                {"url": "https://new.com", "novelty": "NEW"},
                {"url": "https://dup.com", "novelty": "DUPLICATE"},
                {"url": "https://upd.com", "novelty": "UPDATE"},
            ]
        }
        cs.community_signal(state)
        urls = {a["url"] for a in received["articles"]}
        assert urls == {"https://new.com", "https://upd.com"}

    def test_returns_full_summarized_list_unfiltered(self, monkeypatch):
        monkeypatch.setattr(cs, "enrich_with_community", lambda articles: None)
        state = {
            "summarized": [
                {"url": "https://new.com", "novelty": "NEW"},
                {"url": "https://dup.com", "novelty": "DUPLICATE"},
            ]
        }
        result = cs.community_signal(state)
        assert len(result["summarized"]) == 2

    def test_logs_without_crashing_when_no_article_has_hn_points(self, monkeypatch):
        monkeypatch.setattr(cs, "enrich_with_community", lambda articles: None)
        state = {"summarized": [{"url": "https://a.com", "novelty": "NEW"}]}
        result = cs.community_signal(state)  # ne doit pas lever
        assert result["summarized"][0]["url"] == "https://a.com"
