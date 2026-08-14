"""Tests de l'API FastAPI via TestClient.

`src.api.routes` cree son propre `repo = Repository(settings.db_path)` au
niveau module (des l'import). On monkeypatch cette instance de module pour
qu'elle pointe vers une base de test isolee, et on mocke `run_daily_digest`/
`run_custom_search` pour ne jamais declencher de vrai reseau/LLM depuis un
test d'API.
"""

import pytest
from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.app.main import app


@pytest.fixture
def client(repo, monkeypatch):
    monkeypatch.setattr(routes_module, "repo", repo)
    return TestClient(app)


class TestHealth:
    def test_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestDigestToday:
    def test_none_when_no_run(self, client):
        resp = client.get("/api/digest/today")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "none"
        assert body["articles"] == []

    def test_reflects_existing_run_and_articles(self, client, repo, article_factory):
        from src.db.repository import today_str

        today = today_str()
        repo.try_start_run(today)
        repo.save_articles(today, [article_factory(title="Aujourd'hui")])
        repo.finish_run(today, "done")

        resp = client.get("/api/digest/today")
        body = resp.json()
        assert body["status"] == "done"
        assert body["run_date"] == today
        assert len(body["articles"]) == 1
        assert body["articles"][0]["title"] == "Aujourd'hui"


class TestDigestByDate:
    def test_valid_but_unknown_date_returns_none(self, client):
        resp = client.get("/api/digest/2020-01-01")
        assert resp.status_code == 200
        assert resp.json()["status"] == "none"

    def test_invalid_date_format_returns_400(self, client):
        resp = client.get("/api/digest/not-a-date")
        assert resp.status_code == 400

    def test_existing_date_returns_articles(self, client, repo, article_factory):
        repo.try_start_run("2026-08-10")
        repo.save_articles("2026-08-10", [article_factory()])
        repo.finish_run("2026-08-10", "done")

        resp = client.get("/api/digest/2026-08-10")
        assert resp.status_code == 200
        assert len(resp.json()["articles"]) == 1


class TestHistory:
    def test_empty_history(self, client):
        resp = client.get("/api/history")
        assert resp.status_code == 200
        assert resp.json() == {"days": []}

    def test_reflects_repo_history_index(self, client, repo, article_factory):
        repo.try_start_run("2026-08-10")
        repo.save_articles("2026-08-10", [article_factory()])
        repo.finish_run("2026-08-10", "done")

        resp = client.get("/api/history")
        days = resp.json()["days"]
        assert len(days) == 1
        assert days[0]["run_date"] == "2026-08-10"
        assert days[0]["count"] == 1


class TestPostRun:
    def test_starts_when_no_run_exists(self, client, monkeypatch):
        monkeypatch.setattr(routes_module, "run_daily_digest", lambda repo, force: None)
        resp = client.post("/api/run")
        assert resp.status_code == 200
        assert resp.json()["action"] == "started"

    def test_already_running_returns_that_status(self, client, repo):
        from src.db.repository import today_str

        repo.try_start_run(today_str())  # laisse le run a l'etat 'running'
        resp = client.post("/api/run")
        assert resp.json()["action"] == "already_running"

    def test_done_without_force_is_skipped(self, client, repo):
        from src.db.repository import today_str

        today = today_str()
        repo.try_start_run(today)
        repo.finish_run(today, "done")

        resp = client.post("/api/run")
        assert resp.json()["action"] == "skipped"

    def test_done_with_force_restarts(self, client, repo, monkeypatch):
        from src.db.repository import today_str

        today = today_str()
        repo.try_start_run(today)
        repo.finish_run(today, "done")

        monkeypatch.setattr(routes_module, "run_daily_digest", lambda repo, force: None)
        resp = client.post("/api/run?force=true")
        assert resp.json()["action"] == "started"


class TestPostSearch:
    def test_happy_path(self, client, monkeypatch):
        monkeypatch.setattr(
            routes_module,
            "run_custom_search",
            lambda repo, query: [{"url": "https://a.com", "title": "A"}],
        )
        resp = client.post("/api/search", json={"query": "RAG avec pgvector"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "RAG avec pgvector"
        assert body["count"] == 1
        assert body["articles"][0]["title"] == "A"

    def test_missing_query_field_is_422(self, client):
        resp = client.post("/api/search", json={})
        assert resp.status_code == 422

    def test_empty_query_string_is_422(self, client):
        # Pydantic Field(min_length=1) rejette "" avant meme d'atteindre le handler.
        resp = client.post("/api/search", json={"query": ""})
        assert resp.status_code == 422

    def test_whitespace_only_query_is_400(self, client):
        # Passe la validation Pydantic (longueur 3) mais se vide au .strip() du handler.
        resp = client.post("/api/search", json={"query": "   "})
        assert resp.status_code == 400
        assert "vide" in resp.json()["detail"]

    def test_query_too_long_is_422(self, client):
        resp = client.post("/api/search", json={"query": "x" * 301})
        assert resp.status_code == 422

    def test_query_at_max_length_is_accepted(self, client, monkeypatch):
        monkeypatch.setattr(routes_module, "run_custom_search", lambda repo, query: [])
        resp = client.post("/api/search", json={"query": "x" * 300})
        assert resp.status_code == 200

    def test_search_failure_returns_500(self, client, monkeypatch):
        def _boom(repo, query):
            raise RuntimeError("recherche indisponible")

        monkeypatch.setattr(routes_module, "run_custom_search", _boom)
        resp = client.post("/api/search", json={"query": "test"})
        assert resp.status_code == 500
        assert "recherche indisponible" in resp.json()["detail"]

    def test_query_is_stripped_in_response(self, client, monkeypatch):
        monkeypatch.setattr(routes_module, "run_custom_search", lambda repo, query: [])
        resp = client.post("/api/search", json={"query": "  spaced query  "})
        assert resp.json()["query"] == "spaced query"
