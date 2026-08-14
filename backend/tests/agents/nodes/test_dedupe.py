"""Tests du node dedupe."""

from src.agents.nodes.dedupe import dedupe


class TestDedupe:
    def test_no_candidates_returns_empty(self):
        assert dedupe({})["deduped"] == []

    def test_keeps_unique_candidates(self):
        state = {
            "raw_candidates": [
                {"url": "https://a.com/1", "snippet": "a"},
                {"url": "https://b.com/2", "snippet": "b"},
            ]
        }
        result = dedupe(state)
        assert len(result["deduped"]) == 2

    def test_removes_exact_duplicate_url(self):
        state = {
            "raw_candidates": [
                {"url": "https://a.com/1", "snippet": "short"},
                {"url": "https://a.com/1", "snippet": "short"},
            ]
        }
        result = dedupe(state)
        assert len(result["deduped"]) == 1

    def test_inter_provider_duplicate_keeps_longer_snippet(self):
        state = {
            "raw_candidates": [
                {"url": "https://a.com/1", "snippet": "short", "provider": "exa"},
                {
                    "url": "https://a.com/1",
                    "snippet": "a much longer and more detailed snippet",
                    "provider": "brave",
                },
            ]
        }
        result = dedupe(state)
        assert len(result["deduped"]) == 1
        assert result["deduped"][0]["snippet"] == "a much longer and more detailed snippet"

    def test_equivalent_urls_normalize_to_same_key(self):
        state = {
            "raw_candidates": [
                {"url": "https://www.a.com/1?utm_source=x", "snippet": ""},
                {"url": "https://a.com/1", "snippet": ""},
            ]
        }
        result = dedupe(state)
        assert len(result["deduped"]) == 1

    def test_excludes_urls_already_in_history(self):
        state = {
            "raw_candidates": [{"url": "https://a.com/1", "snippet": ""}],
            "recent_history": [{"normalized_url": "https://a.com/1"}],
        }
        result = dedupe(state)
        assert result["deduped"] == []

    def test_empty_history_excludes_nothing(self):
        state = {
            "raw_candidates": [{"url": "https://a.com/1", "snippet": ""}],
            "recent_history": [],
        }
        result = dedupe(state)
        assert len(result["deduped"]) == 1

    def test_missing_or_empty_url_skipped(self):
        state = {
            "raw_candidates": [
                {"url": "", "snippet": "x"},
                {"snippet": "no url key"},
                {"url": "https://a.com/1", "snippet": "kept"},
            ]
        }
        result = dedupe(state)
        assert len(result["deduped"]) == 1
        assert result["deduped"][0]["url"] == "https://a.com/1"

    def test_normalized_url_field_is_attached(self):
        state = {"raw_candidates": [{"url": "https://WWW.A.com/1/", "snippet": ""}]}
        result = dedupe(state)
        assert result["deduped"][0]["normalized_url"] == "https://a.com/1"

    def test_history_with_missing_normalized_url_key_ignored_safely(self):
        state = {
            "raw_candidates": [{"url": "https://a.com/1", "snippet": ""}],
            "recent_history": [{"title": "no normalized_url key"}],
        }
        result = dedupe(state)
        assert len(result["deduped"]) == 1
