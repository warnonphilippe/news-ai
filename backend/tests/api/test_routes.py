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


def _stub_search(repo, query):
    """Reponse minimale d'une recherche memorisee (forme du service reel)."""
    return {
        "id": 1,
        "query": query,
        "created_at": "2026-08-14T10:00:00",
        "count": 0,
        "articles": [],
    }


class TestPostSearch:
    def test_happy_path(self, client, monkeypatch):
        monkeypatch.setattr(
            routes_module,
            "run_custom_search",
            lambda repo, query: {
                "id": 3,
                "query": query,
                "created_at": "2026-08-14T10:00:00",
                "count": 1,
                "articles": [{"url": "https://a.com", "title": "A"}],
            },
        )
        resp = client.post("/api/search", json={"query": "RAG avec pgvector"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 3
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
        monkeypatch.setattr(routes_module, "run_custom_search", _stub_search)
        resp = client.post("/api/search", json={"query": "x" * 300})
        assert resp.status_code == 200

    def test_search_failure_returns_500(self, client, monkeypatch):
        def _boom(repo, query):
            raise RuntimeError("recherche indisponible")

        monkeypatch.setattr(routes_module, "run_custom_search", _boom)
        resp = client.post("/api/search", json={"query": "test"})
        assert resp.status_code == 500
        assert "recherche indisponible" in resp.json()["detail"]

    def test_query_is_stripped_before_reaching_the_service(self, client, monkeypatch):
        seen = {}

        def _capture(repo, query):
            seen["query"] = query
            return _stub_search(repo, query)

        monkeypatch.setattr(routes_module, "run_custom_search", _capture)
        resp = client.post("/api/search", json={"query": "  spaced query  "})
        assert seen["query"] == "spaced query"
        assert resp.json()["query"] == "spaced query"


class TestSearchesCrud:
    """Endpoints de gestion des recherches memorisees (liste / relecture /
    suppression). On ecrit directement via le repo : ces routes ne declenchent
    aucune recherche, elles ne font que lire/supprimer."""

    def test_list_is_empty_initially(self, client):
        resp = client.get("/api/searches")
        assert resp.status_code == 200
        assert resp.json() == {"searches": []}

    def test_list_returns_stored_searches(self, client, repo, article_factory):
        repo.save_custom_search("premiere", [article_factory()])
        repo.save_custom_search("seconde", [])

        resp = client.get("/api/searches")
        searches = resp.json()["searches"]
        assert {s["query"] for s in searches} == {"premiere", "seconde"}
        by_query = {s["query"]: s for s in searches}
        assert by_query["premiere"]["count"] == 1
        assert by_query["seconde"]["count"] == 0

    def test_get_returns_the_search_and_its_articles(self, client, repo, article_factory):
        sid = repo.save_custom_search("ma requete", [article_factory(title="A")])

        resp = client.get(f"/api/searches/{sid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == sid
        assert body["query"] == "ma requete"
        assert body["count"] == 1
        assert body["articles"][0]["title"] == "A"

    def test_get_unknown_id_is_404(self, client):
        assert client.get("/api/searches/999").status_code == 404

    def test_get_non_integer_id_is_422(self, client):
        assert client.get("/api/searches/abc").status_code == 422

    def test_delete_removes_the_search(self, client, repo, article_factory):
        sid = repo.save_custom_search("a supprimer", [article_factory()])

        resp = client.delete(f"/api/searches/{sid}")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": sid}
        assert client.get(f"/api/searches/{sid}").status_code == 404
        assert client.get("/api/searches").json()["searches"] == []

    def test_delete_unknown_id_is_404(self, client):
        assert client.delete("/api/searches/999").status_code == 404

    def test_delete_is_not_idempotent_second_call_is_404(self, client, repo):
        sid = repo.save_custom_search("q", [])
        assert client.delete(f"/api/searches/{sid}").status_code == 200
        assert client.delete(f"/api/searches/{sid}").status_code == 404

    def test_deleting_one_search_leaves_the_others(self, client, repo, article_factory):
        keep = repo.save_custom_search("a garder", [article_factory()])
        drop = repo.save_custom_search("a jeter", [article_factory()])

        client.delete(f"/api/searches/{drop}")

        remaining = client.get("/api/searches").json()["searches"]
        assert [s["id"] for s in remaining] == [keep]
        assert client.get(f"/api/searches/{keep}").json()["count"] == 1

    def test_stored_searches_never_appear_in_the_daily_digest(
        self, client, repo, article_factory
    ):
        from src.db.repository import today_str

        repo.save_custom_search("recherche perso", [article_factory(title="Perso")])

        assert client.get("/api/digest/today").json()["articles"] == []
        assert client.get("/api/history").json()["days"] == []
        assert repo.get_recent_history(30, before_date=today_str()) == []
