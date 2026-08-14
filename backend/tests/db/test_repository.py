"""Tests de src.db.repository — Repository (verrou, historique, persist).

Note : `articles.run_date` porte une contrainte FOREIGN KEY vers `runs.run_date`
(le schema le reflete l'usage reel : `persist` n'est appele qu'apres
`try_start_run`). Le helper `_save` ci-dessous cree systematiquement le run
parent avant d'inserer des articles, pour respecter cette contrainte.
"""

from src.db.repository import Repository, today_str


def _save(repo: Repository, run_date: str, articles) -> None:
    """Sauvegarde des articles en creant d'abord le run parent (contrainte FK)."""
    repo.try_start_run(run_date)
    repo.save_articles(run_date, articles)


class TestTodayStr:
    def test_returns_iso_format(self):
        import re

        assert re.match(r"^\d{4}-\d{2}-\d{2}$", today_str())


class TestTryStartRun:
    def test_first_call_returns_true(self, repo):
        assert repo.try_start_run("2026-08-14") is True

    def test_second_call_same_date_returns_false(self, repo):
        assert repo.try_start_run("2026-08-14") is True
        assert repo.try_start_run("2026-08-14") is False

    def test_different_dates_are_independent(self, repo):
        assert repo.try_start_run("2026-08-14") is True
        assert repo.try_start_run("2026-08-15") is True

    def test_run_status_is_running_after_start(self, repo):
        repo.try_start_run("2026-08-14")
        run = repo.get_run("2026-08-14")
        assert run["status"] == "running"
        assert run["started_at"] is not None


class TestGetRun:
    def test_returns_none_when_absent(self, repo):
        assert repo.get_run("2026-08-14") is None

    def test_returns_dict_when_present(self, repo):
        repo.try_start_run("2026-08-14")
        run = repo.get_run("2026-08-14")
        assert isinstance(run, dict)
        assert run["run_date"] == "2026-08-14"


class TestFinishRun:
    def test_updates_status_and_finished_at(self, repo):
        repo.try_start_run("2026-08-14")
        repo.finish_run("2026-08-14", status="done")
        run = repo.get_run("2026-08-14")
        assert run["status"] == "done"
        assert run["finished_at"] is not None
        assert run["error"] is None

    def test_records_error_message(self, repo):
        repo.try_start_run("2026-08-14")
        repo.finish_run("2026-08-14", status="error", error="boom")
        run = repo.get_run("2026-08-14")
        assert run["status"] == "error"
        assert run["error"] == "boom"


class TestResetRun:
    def test_deletes_run_and_its_articles(self, repo, article_factory):
        _save(repo, "2026-08-14", [article_factory()])
        assert repo.get_run("2026-08-14") is not None
        assert len(repo.get_digest("2026-08-14")) == 1

        repo.reset_run("2026-08-14")

        assert repo.get_run("2026-08-14") is None
        assert repo.get_digest("2026-08-14") == []

    def test_reset_nonexistent_run_does_not_raise(self, repo):
        repo.reset_run("2026-08-14")


class TestSaveAndGetDigest:
    def test_round_trip_basic_fields(self, repo, article_factory):
        art = article_factory(title="Mon article", url="https://x.com/a")
        _save(repo, "2026-08-14", [art])

        digest = repo.get_digest("2026-08-14")
        assert len(digest) == 1
        assert digest[0]["title"] == "Mon article"
        assert digest[0]["url"] == "https://x.com/a"
        assert digest[0]["rank"] == 1

    def test_rank_assigned_by_insertion_order(self, repo, article_factory):
        arts = [
            article_factory(url="https://x.com/1", title="First"),
            article_factory(url="https://x.com/2", title="Second"),
            article_factory(url="https://x.com/3", title="Third"),
        ]
        _save(repo, "2026-08-14", arts)

        digest = repo.get_digest("2026-08-14")
        assert [d["rank"] for d in digest] == [1, 2, 3]
        assert [d["title"] for d in digest] == ["First", "Second", "Third"]

    def test_tags_and_links_json_round_trip(self, repo, article_factory):
        art = article_factory(
            tags=["AI", "Java"], links=[{"title": "Doc", "url": "https://d.com"}]
        )
        _save(repo, "2026-08-14", [art])

        digest = repo.get_digest("2026-08-14")
        assert digest[0]["tags"] == ["AI", "Java"]
        assert digest[0]["links"] == [{"title": "Doc", "url": "https://d.com"}]

    def test_empty_tags_and_links_round_trip_as_empty_lists(self, repo, article_factory):
        art = article_factory(tags=[], links=[])
        _save(repo, "2026-08-14", [art])
        digest = repo.get_digest("2026-08-14")
        assert digest[0]["tags"] == []
        assert digest[0]["links"] == []

    def test_scoring_columns_round_trip(self, repo, article_factory):
        art = article_factory(
            relevance=88,
            relevance_rationale="Tres pertinent",
            age_days=3,
            freshness_factor=0.9,
            source_factor=1.15,
            community_factor=1.05,
            hn_points=42,
            hn_comments=7,
            final_score=95.5,
        )
        _save(repo, "2026-08-14", [art])
        digest = repo.get_digest("2026-08-14")
        d = digest[0]
        assert d["relevance"] == 88
        assert d["relevance_rationale"] == "Tres pertinent"
        assert d["age_days"] == 3
        assert d["freshness_factor"] == 0.9
        assert d["source_factor"] == 1.15
        assert d["community_factor"] == 1.05
        assert d["hn_points"] == 42
        assert d["hn_comments"] == 7
        assert d["final_score"] == 95.5

    def test_missing_optional_fields_default_gracefully(self, repo):
        # Un article minimal (sans tags/links/scoring) ne doit pas faire echouer l'insertion.
        _save(repo, "2026-08-14", [{"title": "Minimal", "summary": "S"}])
        digest = repo.get_digest("2026-08-14")
        assert digest[0]["title"] == "Minimal"
        assert digest[0]["url"] == ""
        assert digest[0]["tags"] == []
        assert digest[0]["relevance"] is None

    def test_is_update_of_stored_and_retrieved(self, repo, article_factory):
        _save(repo, "2026-08-13", [article_factory(url="https://x.com/prev")])
        prev = repo.get_digest("2026-08-13")[0]

        _save(
            repo,
            "2026-08-14",
            [article_factory(url="https://x.com/next", is_update_of=prev["id"])],
        )
        digest = repo.get_digest("2026-08-14")
        assert digest[0]["is_update_of"] == prev["id"]

    def test_get_digest_empty_when_no_run(self, repo):
        assert repo.get_digest("2026-08-14") == []

    def test_save_empty_list_is_a_noop(self, repo):
        _save(repo, "2026-08-14", [])
        assert repo.get_digest("2026-08-14") == []

    def test_save_without_parent_run_violates_foreign_key(self, repo, article_factory):
        """Documente la contrainte : sauvegarder sans run parent leve une erreur.

        C'est le comportement attendu — persist() n'est appele qu'apres
        try_start_run() dans le pipeline reel (cf. service.run_daily_digest).
        """
        import sqlite3

        import pytest

        with pytest.raises(sqlite3.IntegrityError):
            repo.save_articles("2026-08-14", [article_factory()])


class TestGetRecentHistory:
    def test_excludes_articles_on_or_after_before_date(self, repo, article_factory):
        _save(repo, "2026-08-14", [article_factory(url="https://x.com/today")])
        history = repo.get_recent_history(14, before_date="2026-08-14")
        assert history == []  # 'today' n'est pas < before_date

    def test_includes_articles_strictly_before(self, repo, article_factory):
        _save(repo, "2026-08-13", [article_factory(url="https://x.com/yesterday")])
        history = repo.get_recent_history(14, before_date="2026-08-14")
        assert len(history) == 1

    def test_excludes_articles_older_than_window(self, repo, article_factory):
        _save(repo, "2026-07-01", [article_factory(url="https://x.com/old")])
        history = repo.get_recent_history(14, before_date="2026-08-14")
        assert history == []

    def test_boundary_exactly_at_window_is_included(self, repo, article_factory):
        # since = before_date - 14 jours ; 'since' lui-meme est inclus (>=).
        _save(repo, "2026-07-31", [article_factory(url="https://x.com/boundary")])
        history = repo.get_recent_history(14, before_date="2026-08-14")
        assert len(history) == 1

    def test_ordering_most_recent_first(self, repo, article_factory):
        _save(repo, "2026-08-10", [article_factory(url="https://x.com/a")])
        _save(repo, "2026-08-12", [article_factory(url="https://x.com/b")])
        history = repo.get_recent_history(14, before_date="2026-08-14")
        assert [h["run_date"] for h in history] == ["2026-08-12", "2026-08-10"]

    def test_returns_compact_shape(self, repo, article_factory):
        _save(repo, "2026-08-12", [article_factory()])
        history = repo.get_recent_history(14, before_date="2026-08-14")
        assert set(history[0].keys()) == {
            "id",
            "run_date",
            "url",
            "normalized_url",
            "title",
            "summary",
            "topic_cluster",
        }

    def test_default_before_date_is_today(self, repo, article_factory, monkeypatch):
        from datetime import date

        import src.db.repository as repo_module

        fixed_today = date(2026, 8, 14)

        class _FixedDate(date):
            @classmethod
            def today(cls):
                return fixed_today

        monkeypatch.setattr(repo_module, "date", _FixedDate)
        _save(repo, "2026-08-13", [article_factory()])
        history = repo.get_recent_history(14)  # before_date omis
        assert len(history) == 1


class TestKnownNormalizedUrls:
    def test_returns_set_of_normalized_urls(self, repo, article_factory):
        _save(
            repo,
            "2026-08-12",
            [
                article_factory(url="https://x.com/a", normalized_url="https://x.com/a"),
                article_factory(url="https://x.com/b", normalized_url="https://x.com/b"),
            ],
        )
        urls = repo.known_normalized_urls(14, before_date="2026-08-14")
        assert urls == {"https://x.com/a", "https://x.com/b"}


class TestGetHistoryIndex:
    def test_counts_articles_per_run(self, repo, article_factory):
        repo.try_start_run("2026-08-14")
        repo.save_articles(
            "2026-08-14",
            [article_factory(url="https://x.com/1"), article_factory(url="https://x.com/2")],
        )
        repo.finish_run("2026-08-14", "done")

        index = repo.get_history_index(14)
        assert len(index) == 1
        assert index[0]["run_date"] == "2026-08-14"
        assert index[0]["count"] == 2
        assert index[0]["status"] == "done"

    def test_run_with_zero_articles_still_appears_with_count_zero(self, repo):
        repo.try_start_run("2026-08-14")
        repo.finish_run("2026-08-14", "done")

        index = repo.get_history_index(14)
        assert index[0]["count"] == 0

    def test_excludes_runs_outside_window(self, repo):
        repo.try_start_run("2020-01-01")
        index = repo.get_history_index(14)
        assert index == []

    def test_ordered_most_recent_first(self, repo):
        repo.try_start_run("2026-08-10")
        repo.try_start_run("2026-08-12")
        index = repo.get_history_index(14)
        assert [r["run_date"] for r in index] == ["2026-08-12", "2026-08-10"]


class TestCustomSearches:
    """Recherches personnalisees : tables dediees, etanches vis-a-vis du digest."""

    def test_save_returns_a_new_id(self, repo, article_factory):
        sid = repo.save_custom_search("q", [article_factory()])
        assert isinstance(sid, int)
        assert sid > 0

    def test_ids_are_distinct_for_identical_queries(self, repo):
        first = repo.save_custom_search("meme phrase", [])
        second = repo.save_custom_search("meme phrase", [])
        assert first != second

    def test_saving_does_not_replace_previous_searches(self, repo):
        repo.save_custom_search("premiere", [])
        repo.save_custom_search("seconde", [])
        assert len(repo.list_custom_searches()) == 2

    def test_list_is_empty_initially(self, repo):
        assert repo.list_custom_searches() == []

    def test_list_counts_articles_per_search(self, repo, article_factory):
        with_two = repo.save_custom_search(
            "deux", [article_factory(url="https://a.com"), article_factory(url="https://b.com")]
        )
        empty = repo.save_custom_search("zero", [])

        by_id = {s["id"]: s for s in repo.list_custom_searches()}
        assert by_id[with_two]["count"] == 2
        assert by_id[empty]["count"] == 0

    def test_list_exposes_query_and_created_at(self, repo):
        repo.save_custom_search("ma requete", [])
        entry = repo.list_custom_searches()[0]
        assert entry["query"] == "ma requete"
        assert entry["created_at"]  # horodatage renseigne

    def test_get_returns_articles_ordered_by_rank(self, repo, article_factory):
        sid = repo.save_custom_search(
            "q",
            [
                article_factory(url="https://1.com", title="Premier"),
                article_factory(url="https://2.com", title="Deuxieme"),
                article_factory(url="https://3.com", title="Troisieme"),
            ],
        )
        found = repo.get_custom_search(sid)
        assert [a["rank"] for a in found["articles"]] == [1, 2, 3]
        assert [a["title"] for a in found["articles"]] == [
            "Premier",
            "Deuxieme",
            "Troisieme",
        ]

    def test_get_deserialises_tags_and_links(self, repo, article_factory):
        sid = repo.save_custom_search(
            "q",
            [article_factory(tags=["A", "B"], links=[{"title": "T", "url": "u"}])],
        )
        art = repo.get_custom_search(sid)["articles"][0]
        assert art["tags"] == ["A", "B"]
        assert art["links"] == [{"title": "T", "url": "u"}]

    def test_get_normalises_run_date_and_is_update_of_to_none(self, repo, article_factory):
        # Une recherche n'appartient a aucun run et ne complete jamais un sujet
        # passe : la forme retournee doit l'affirmer explicitement.
        sid = repo.save_custom_search("q", [article_factory(is_update_of=42)])
        art = repo.get_custom_search(sid)["articles"][0]
        assert art["run_date"] is None
        assert art["is_update_of"] is None
        assert "search_id" not in art

    def test_get_preserves_scoring_components(self, repo, article_factory):
        sid = repo.save_custom_search(
            "q",
            [article_factory(relevance=91, freshness_factor=0.5, final_score=45.5)],
        )
        art = repo.get_custom_search(sid)["articles"][0]
        assert art["relevance"] == 91
        assert art["freshness_factor"] == 0.5
        assert art["final_score"] == 45.5

    def test_get_unknown_id_returns_none(self, repo):
        assert repo.get_custom_search(12345) is None

    def test_get_search_without_articles(self, repo):
        sid = repo.save_custom_search("aucun resultat", [])
        found = repo.get_custom_search(sid)
        assert found["count"] == 0
        assert found["articles"] == []

    def test_delete_returns_true_and_removes_it(self, repo, article_factory):
        sid = repo.save_custom_search("q", [article_factory()])
        assert repo.delete_custom_search(sid) is True
        assert repo.get_custom_search(sid) is None
        assert repo.list_custom_searches() == []

    def test_delete_unknown_id_returns_false(self, repo):
        assert repo.delete_custom_search(999) is False

    def test_delete_also_removes_the_articles(self, repo, article_factory):
        sid = repo.save_custom_search("q", [article_factory()])
        repo.delete_custom_search(sid)

        from src.db.models import get_connection

        conn = get_connection(repo.db_path)
        try:
            left = conn.execute(
                "SELECT COUNT(*) AS n FROM custom_search_articles WHERE search_id = ?",
                (sid,),
            ).fetchone()["n"]
        finally:
            conn.close()
        assert left == 0

    def test_delete_leaves_other_searches_intact(self, repo, article_factory):
        keep = repo.save_custom_search("a garder", [article_factory()])
        drop = repo.save_custom_search("a jeter", [article_factory()])

        repo.delete_custom_search(drop)

        assert [s["id"] for s in repo.list_custom_searches()] == [keep]
        assert repo.get_custom_search(keep)["count"] == 1

    def test_never_pollutes_the_digest_or_anti_redite(self, repo, article_factory):
        # Garantie structurelle : tables separees de runs/articles.
        repo.save_custom_search("q", [article_factory(url="https://perso.com")])

        assert repo.get_digest(today_str()) == []
        assert repo.get_history_index(14) == []
        assert repo.get_recent_history(30) == []
        assert repo.known_normalized_urls(30) == set()

    def test_survives_a_new_repository_instance(self, repo, article_factory, db_path):
        # La persistance est le point de la fonctionnalite : une nouvelle
        # instance (= redemarrage du backend) doit relire les memes donnees.
        sid = repo.save_custom_search("persistante", [article_factory(title="A")])

        from src.db.repository import Repository

        reopened = Repository(db_path)
        found = reopened.get_custom_search(sid)
        assert found["query"] == "persistante"
        assert [a["title"] for a in found["articles"]] == ["A"]
