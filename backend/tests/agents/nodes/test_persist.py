"""Tests du node persist."""

from src.agents.nodes.persist import make_persist


class TestPersist:
    def test_saves_selected_articles_to_repo(self, repo):
        repo.try_start_run("2026-08-14")
        persist = make_persist(repo)
        state = {
            "run_date": "2026-08-14",
            "selected": [
                {"url": "https://a.com", "title": "T", "summary": "S"},
            ],
        }
        result = persist(state)
        assert result == {}
        digest = repo.get_digest("2026-08-14")
        assert len(digest) == 1
        assert digest[0]["title"] == "T"

    def test_missing_links_defaults_to_empty_list(self, repo):
        repo.try_start_run("2026-08-14")
        persist = make_persist(repo)
        state = {"run_date": "2026-08-14", "selected": [{"url": "https://a.com"}]}
        persist(state)
        digest = repo.get_digest("2026-08-14")
        assert digest[0]["links"] == []

    def test_existing_links_preserved(self, repo):
        repo.try_start_run("2026-08-14")
        persist = make_persist(repo)
        links = [{"title": "Doc", "url": "https://d.com"}]
        state = {
            "run_date": "2026-08-14",
            "selected": [{"url": "https://a.com", "links": links}],
        }
        persist(state)
        digest = repo.get_digest("2026-08-14")
        assert digest[0]["links"] == links

    def test_empty_selected_saves_nothing(self, repo):
        repo.try_start_run("2026-08-14")
        persist = make_persist(repo)
        persist({"run_date": "2026-08-14", "selected": []})
        assert repo.get_digest("2026-08-14") == []

    def test_missing_selected_key_treated_as_empty(self, repo):
        repo.try_start_run("2026-08-14")
        persist = make_persist(repo)
        persist({"run_date": "2026-08-14"})
        assert repo.get_digest("2026-08-14") == []
