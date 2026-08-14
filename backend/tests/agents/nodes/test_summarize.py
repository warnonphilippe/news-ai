"""Tests du node summarize."""

from src.agents.nodes import summarize as sm
from src.agents.state import ArticleSummary


class TestCap:
    def test_default_uses_settings_max_articles(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        assert sm._cap({}) == 15  # max(5*3, 9)

    def test_small_max_articles_floors_at_nine(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 1)
        assert sm._cap({}) == 9  # max(1*3, 9)

    def test_state_override_used_when_present(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        assert sm._cap({"max_articles": 10}) == 30  # max(10*3, 9), pas 15


class TestSummarize:
    def test_no_candidates_returns_empty(self):
        assert sm.summarize({"deduped": []}) == {"summarized": []}

    def test_missing_deduped_key_treated_as_empty(self):
        assert sm.summarize({}) == {"summarized": []}

    def test_happy_path_enriches_candidate(self, patch_llm, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        patch_llm(
            sm,
            lambda _pv: ArticleSummary(
                summary="Un resume.",
                why_it_matters="Ca compte.",
                tags=["AI", "Java"],
                topic_cluster="Claude Code",
            ),
        )

        state = {
            "deduped": [
                {"url": "https://a.com", "title": "T", "source": "a.com", "snippet": "extrait"}
            ]
        }
        result = sm.summarize(state)
        art = result["summarized"][0]
        assert art["summary"] == "Un resume."
        assert art["why_it_matters"] == "Ca compte."
        assert art["tags"] == ["AI", "Java"]
        assert art["topic_cluster"] == "Claude Code"
        # Champs d'origine preserves (fusion **cand).
        assert art["url"] == "https://a.com"

    def test_relevance_is_not_set_by_this_node(self, patch_llm, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        patch_llm(
            sm,
            lambda _pv: ArticleSummary(
                summary="s", why_it_matters="w", tags=[], topic_cluster="c"
            ),
        )
        state = {"deduped": [{"url": "https://a.com", "title": "T"}]}
        result = sm.summarize(state)
        assert "relevance" not in result["summarized"][0]

    def test_one_candidate_failure_does_not_drop_others(self, patch_llm, monkeypatch):
        from src.config.settings import settings
        from tests.conftest import prompt_text

        monkeypatch.setattr(settings, "max_articles_per_day", 5)

        def _result_fn(pv):
            text = prompt_text(pv)
            if "FAIL_MARKER" in text:
                return RuntimeError("resume impossible")
            return ArticleSummary(
                summary="ok", why_it_matters="ok", tags=[], topic_cluster="c"
            )

        patch_llm(sm, _result_fn)

        state = {
            "deduped": [
                {"url": "https://FAIL_MARKER.example", "title": "Failing"},
                {"url": "https://ok.example", "title": "Working"},
            ]
        }
        result = sm.summarize(state)
        assert len(result["summarized"]) == 1
        assert result["summarized"][0]["url"] == "https://ok.example"

    def test_candidates_truncated_to_cap(self, patch_llm, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 1)  # cap = max(3,9) = 9
        patch_llm(
            sm,
            lambda _pv: ArticleSummary(
                summary="s", why_it_matters="w", tags=[], topic_cluster="c"
            ),
        )
        candidates = [{"url": f"https://a.com/{i}", "title": f"T{i}"} for i in range(15)]
        result = sm.summarize({"deduped": candidates})
        assert len(result["summarized"]) == 9

    def test_missing_snippet_uses_placeholder(self, patch_llm, monkeypatch):
        from src.config.settings import settings
        from tests.conftest import prompt_text

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        captured = {}

        def _capture(pv):
            captured["text"] = prompt_text(pv)
            return ArticleSummary(summary="s", why_it_matters="w", tags=[], topic_cluster="c")

        patch_llm(sm, _capture)
        sm.summarize({"deduped": [{"url": "https://a.com", "title": "T"}]})
        assert "pas d'extrait disponible" in captured["text"]
