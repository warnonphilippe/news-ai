"""Tests de src.agents.service — orchestration run_daily_digest / run_custom_search."""

import pytest

from src.agents import service


class TestRunDailyDigest:
    def test_first_call_starts_and_completes(self, repo, monkeypatch):
        monkeypatch.setattr(service, "run_digest", lambda repo, run_date: None)
        result = service.run_daily_digest(repo)
        assert result["status"] == "done"
        assert result["action"] == "started"

    def test_second_call_same_day_is_skipped(self, repo, monkeypatch):
        calls = {"count": 0}

        def _fake_run_digest(repo, run_date):
            calls["count"] += 1

        monkeypatch.setattr(service, "run_digest", _fake_run_digest)

        service.run_daily_digest(repo)
        result = service.run_daily_digest(repo)

        assert result["action"] == "skipped"
        assert result["status"] == "done"
        assert calls["count"] == 1  # le pipeline n'a tourne qu'une fois

    def test_force_resets_and_reruns(self, repo, monkeypatch):
        calls = {"count": 0}

        def _fake_run_digest(repo, run_date):
            calls["count"] += 1

        monkeypatch.setattr(service, "run_digest", _fake_run_digest)

        service.run_daily_digest(repo)
        result = service.run_daily_digest(repo, force=True)

        assert result["action"] == "started"
        assert calls["count"] == 2

    def test_exception_in_pipeline_marks_run_as_error(self, repo, monkeypatch):
        def _boom(repo, run_date):
            raise RuntimeError("pipeline cassee")

        monkeypatch.setattr(service, "run_digest", _boom)

        result = service.run_daily_digest(repo)

        assert result["status"] == "error"
        assert result["action"] == "error"
        assert "pipeline cassee" in result["error"]

        run = repo.get_run(result["run_date"])
        assert run["status"] == "error"
        assert run["error"] == "pipeline cassee"

    def test_error_does_not_prevent_a_later_force_retry(self, repo, monkeypatch):
        state = {"should_fail": True}

        def _sometimes_fails(repo, run_date):
            if state["should_fail"]:
                raise RuntimeError("echec temporaire")

        monkeypatch.setattr(service, "run_digest", _sometimes_fails)

        first = service.run_daily_digest(repo)
        assert first["status"] == "error"

        state["should_fail"] = False
        second = service.run_daily_digest(repo, force=True)
        assert second["status"] == "done"


class TestRunCustomSearch:
    def test_empty_query_raises_value_error(self, repo):
        with pytest.raises(ValueError):
            service.run_custom_search(repo, "")

    def test_whitespace_only_query_raises_value_error(self, repo):
        with pytest.raises(ValueError):
            service.run_custom_search(repo, "   ")

    def test_none_query_raises_value_error(self, repo):
        with pytest.raises(ValueError):
            service.run_custom_search(repo, None)

    def test_happy_path_returns_ranked_and_ranked_articles(self, repo, monkeypatch):
        fake_graph = _FakeCompiledGraph(
            {"selected": [{"url": "https://a.com"}, {"url": "https://b.com"}]}
        )
        monkeypatch.setattr(service, "build_custom_graph", lambda repo: fake_graph)

        result = service.run_custom_search(repo, "ma recherche")

        assert result["query"] == "ma recherche"
        assert result["count"] == 2
        assert [a["rank"] for a in result["articles"]] == [1, 2]
        assert all(a["is_update_of"] is None for a in result["articles"])
        assert all(a["links"] == [] for a in result["articles"])

    def test_existing_is_update_of_and_links_preserved(self, repo, monkeypatch):
        fake_graph = _FakeCompiledGraph(
            {"selected": [{"url": "https://a.com", "is_update_of": 7, "links": [{"title": "x", "url": "y"}]}]}
        )
        monkeypatch.setattr(service, "build_custom_graph", lambda repo: fake_graph)

        result = service.run_custom_search(repo, "q")
        first = result["articles"][0]
        # is_update_of est toujours neutralise a la relecture : une recherche
        # personnalisee ne complete jamais un sujet passe (pas d'historique
        # fourni au graphe custom).
        assert first["is_update_of"] is None
        assert first["links"] == [{"title": "x", "url": "y"}]

    def test_never_persists_or_locks_a_run(self, repo, monkeypatch):
        fake_graph = _FakeCompiledGraph({"selected": [{"url": "https://a.com"}]})
        monkeypatch.setattr(service, "build_custom_graph", lambda repo: fake_graph)

        service.run_custom_search(repo, "q")

        # Aucun run ni article de DIGEST ne doit exister pour aujourd'hui :
        # la recherche est memorisee dans ses propres tables.
        from src.db.repository import today_str

        assert repo.get_run(today_str()) is None
        assert repo.get_digest(today_str()) == []
        assert repo.get_recent_history(30) == []
        assert len(repo.list_custom_searches()) == 1

    def test_initial_state_uses_custom_search_settings(self, repo, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "custom_search_window_days", 45)
        monkeypatch.setattr(settings, "custom_search_max_results", 12)

        captured = {}

        class _CapturingGraph:
            def invoke(self, initial):
                captured["initial"] = initial
                return {"selected": []}

        monkeypatch.setattr(service, "build_custom_graph", lambda repo: _CapturingGraph())

        service.run_custom_search(repo, "q")
        assert captured["initial"]["search_window_days"] == 45
        assert captured["initial"]["max_articles"] == 12
        assert captured["initial"]["custom_query"] == "q"

    def test_empty_selected_returns_empty_list(self, repo, monkeypatch):
        fake_graph = _FakeCompiledGraph({"selected": []})
        monkeypatch.setattr(service, "build_custom_graph", lambda repo: fake_graph)
        result = service.run_custom_search(repo, "q")
        assert result["articles"] == []
        assert result["count"] == 0

    def test_missing_selected_key_returns_empty_list(self, repo, monkeypatch):
        fake_graph = _FakeCompiledGraph({})
        monkeypatch.setattr(service, "build_custom_graph", lambda repo: fake_graph)
        assert service.run_custom_search(repo, "q")["articles"] == []

    def test_each_call_creates_a_distinct_stored_search(self, repo, monkeypatch):
        fake_graph = _FakeCompiledGraph({"selected": [{"url": "https://a.com"}]})
        monkeypatch.setattr(service, "build_custom_graph", lambda repo: fake_graph)

        first = service.run_custom_search(repo, "meme phrase")
        second = service.run_custom_search(repo, "meme phrase")

        # Meme critere : deux entrees distinctes, la precedente est conservee.
        assert first["id"] != second["id"]
        assert len(repo.list_custom_searches()) == 2

    def test_stored_search_is_readable_afterwards(self, repo, monkeypatch):
        fake_graph = _FakeCompiledGraph(
            {"selected": [{"url": "https://a.com", "title": "T"}]}
        )
        monkeypatch.setattr(service, "build_custom_graph", lambda repo: fake_graph)

        created = service.run_custom_search(repo, "q")
        reread = repo.get_custom_search(created["id"])

        assert reread["query"] == "q"
        assert [a["title"] for a in reread["articles"]] == ["T"]


class _FakeCompiledGraph:
    def __init__(self, final_state):
        self._final_state = final_state

    def invoke(self, initial):
        return self._final_state
