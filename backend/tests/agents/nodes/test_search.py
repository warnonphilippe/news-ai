"""Tests du node search (orchestration Exa+Brave, fallback fenetre)."""

from src.agents.nodes import search as search_module


class TestSearchNode:
    def test_no_queries_returns_empty_with_error(self):
        result = search_module.search({"run_date": "2026-08-14", "queries": []})
        assert result["raw_candidates"] == []
        assert "aucune requete" in result["errors"][0]

    def test_missing_queries_key_treated_as_empty(self):
        result = search_module.search({"run_date": "2026-08-14"})
        assert result["raw_candidates"] == []

    def test_calls_exa_and_brave_for_each_query(self, monkeypatch):
        calls = {"exa": [], "brave": []}

        async def _fake_exa(query, num_results, start_published_date):
            calls["exa"].append((query, start_published_date))
            return [{"url": f"https://exa.com/{query}"}], []

        async def _fake_brave(query, count):
            calls["brave"].append(query)
            return [{"url": f"https://brave.com/{query}"}], []

        monkeypatch.setattr(search_module, "search_exa", _fake_exa)
        monkeypatch.setattr(search_module, "search_brave", _fake_brave)

        state = {"run_date": "2026-08-14", "queries": ["q1", "q2"]}
        result = search_module.search(state)

        assert len(calls["exa"]) == 2
        assert len(calls["brave"]) == 2
        assert len(result["raw_candidates"]) == 4

    def test_start_published_date_uses_settings_window_by_default(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        captured = {}

        async def _fake_exa(query, num_results, start_published_date):
            captured["since"] = start_published_date
            return [], []

        async def _fake_brave(query, count):
            return [], []

        monkeypatch.setattr(search_module, "search_exa", _fake_exa)
        monkeypatch.setattr(search_module, "search_brave", _fake_brave)

        search_module.search({"run_date": "2026-08-14", "queries": ["q"]})
        assert captured["since"] == "2026-08-07"  # 14 aout - 7 jours

    def test_state_window_overrides_settings(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        captured = {}

        async def _fake_exa(query, num_results, start_published_date):
            captured["since"] = start_published_date
            return [], []

        async def _fake_brave(query, count):
            return [], []

        monkeypatch.setattr(search_module, "search_exa", _fake_exa)
        monkeypatch.setattr(search_module, "search_brave", _fake_brave)

        search_module.search(
            {"run_date": "2026-08-14", "search_window_days": 30, "queries": ["q"]}
        )
        assert captured["since"] == "2026-07-15"  # 14 aout - 30 jours

    def test_candidates_without_url_are_filtered_out(self, monkeypatch):
        async def _fake_exa(query, num_results, start_published_date):
            return [{"url": ""}, {"url": "https://ok.com"}], []

        async def _fake_brave(query, count):
            return [{}], []  # pas de cle 'url' du tout

        monkeypatch.setattr(search_module, "search_exa", _fake_exa)
        monkeypatch.setattr(search_module, "search_brave", _fake_brave)

        result = search_module.search({"run_date": "2026-08-14", "queries": ["q"]})
        assert len(result["raw_candidates"]) == 1
        assert result["raw_candidates"][0]["url"] == "https://ok.com"

    def test_errors_from_both_providers_aggregated(self, monkeypatch):
        async def _fake_exa(query, num_results, start_published_date):
            return [], ["exa: boom"]

        async def _fake_brave(query, count):
            return [], ["brave: boom"]

        monkeypatch.setattr(search_module, "search_exa", _fake_exa)
        monkeypatch.setattr(search_module, "search_brave", _fake_brave)

        result = search_module.search({"run_date": "2026-08-14", "queries": ["q"]})
        assert "exa: boom" in result["errors"]
        assert "brave: boom" in result["errors"]

    def test_errors_appended_to_existing_state_errors(self, monkeypatch):
        async def _fake_exa(query, num_results, start_published_date):
            return [], ["exa: boom"]

        async def _fake_brave(query, count):
            return [], []

        monkeypatch.setattr(search_module, "search_exa", _fake_exa)
        monkeypatch.setattr(search_module, "search_brave", _fake_brave)

        result = search_module.search(
            {"run_date": "2026-08-14", "queries": ["q"], "errors": ["earlier error"]}
        )
        assert result["errors"] == ["earlier error", "exa: boom"]
