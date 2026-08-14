"""Tests du node novelty_check."""

from src.agents.nodes import novelty_check as nc
from src.agents.state import NoveltyReport, NoveltyVerdict


class TestNoveltyCheck:
    def test_no_candidates_returns_empty_summarized(self):
        assert nc.novelty_check({"summarized": []}) == {"summarized": []}

    def test_missing_summarized_key_treated_as_empty(self):
        assert nc.novelty_check({}) == {"summarized": []}

    def test_no_history_short_circuits_all_new_without_llm_call(self, monkeypatch):
        called = {"count": 0}

        def _boom(*a, **kw):
            called["count"] += 1
            raise AssertionError("get_llm ne doit pas etre appele sans historique")

        monkeypatch.setattr(nc, "get_llm", _boom)

        state = {
            "summarized": [{"url": "https://a.com", "title": "T", "summary": "S"}],
            "recent_history": [],
        }
        result = nc.novelty_check(state)
        assert result["summarized"][0]["novelty"] == "NEW"
        assert result["summarized"][0]["is_update_of"] is None
        assert called["count"] == 0

    def test_missing_history_key_also_short_circuits(self, monkeypatch):
        def _must_not_be_called(*a, **kw):
            raise AssertionError("get_llm ne doit pas etre appele sans historique")

        monkeypatch.setattr(nc, "get_llm", _must_not_be_called)
        state = {"summarized": [{"url": "https://a.com", "title": "T", "summary": "S"}]}
        result = nc.novelty_check(state)
        assert result["summarized"][0]["novelty"] == "NEW"

    def test_llm_verdicts_applied_per_candidate(self, patch_llm):
        report = NoveltyReport(
            verdicts=[
                NoveltyVerdict(url="https://a.com", verdict="NEW"),
                NoveltyVerdict(url="https://b.com", verdict="DUPLICATE"),
                NoveltyVerdict(url="https://c.com", verdict="UPDATE", is_update_of=42),
            ]
        )
        patch_llm(nc, lambda _pv: report)

        state = {
            "summarized": [
                {"url": "https://a.com", "title": "A", "summary": "sa"},
                {"url": "https://b.com", "title": "B", "summary": "sb"},
                {"url": "https://c.com", "title": "C", "summary": "sc"},
            ],
            "recent_history": [{"id": 42, "run_date": "2026-08-10", "title": "Old"}],
        }
        result = nc.novelty_check(state)
        by_url = {c["url"]: c for c in result["summarized"]}
        assert by_url["https://a.com"]["novelty"] == "NEW"
        assert by_url["https://b.com"]["novelty"] == "DUPLICATE"
        assert by_url["https://c.com"]["novelty"] == "UPDATE"
        assert by_url["https://c.com"]["is_update_of"] == 42

    def test_update_pointing_to_unknown_history_id_is_dropped(self, patch_llm):
        report = NoveltyReport(
            verdicts=[
                NoveltyVerdict(url="https://a.com", verdict="UPDATE", is_update_of=999),
            ]
        )
        patch_llm(nc, lambda _pv: report)

        state = {
            "summarized": [{"url": "https://a.com", "title": "A", "summary": "sa"}],
            "recent_history": [{"id": 1, "run_date": "2026-08-10", "title": "Old"}],
        }
        result = nc.novelty_check(state)
        # Le verdict LLM (UPDATE) est conserve tel quel ; seul is_update_of est
        # ecarte car il ne pointe vers aucun id connu de l'historique.
        assert result["summarized"][0]["novelty"] == "UPDATE"
        assert result["summarized"][0]["is_update_of"] is None

    def test_candidate_missing_from_llm_response_defaults_new(self, patch_llm):
        report = NoveltyReport(verdicts=[])  # LLM n'a rien renvoye
        patch_llm(nc, lambda _pv: report)

        state = {
            "summarized": [{"url": "https://a.com", "title": "A", "summary": "sa"}],
            "recent_history": [{"id": 1, "run_date": "2026-08-10", "title": "Old"}],
        }
        result = nc.novelty_check(state)
        assert result["summarized"][0]["novelty"] == "NEW"
        assert result["summarized"][0]["is_update_of"] is None

    def test_llm_exception_falls_back_to_all_new(self, patch_llm):
        patch_llm(nc, lambda _pv: RuntimeError("LLM indisponible"))

        state = {
            "summarized": [
                {"url": "https://a.com", "title": "A", "summary": "sa"},
                {"url": "https://b.com", "title": "B", "summary": "sb"},
            ],
            "recent_history": [{"id": 1, "run_date": "2026-08-10", "title": "Old"}],
        }
        result = nc.novelty_check(state)
        assert all(c["novelty"] == "NEW" for c in result["summarized"])

    def test_history_formatting_included_in_prompt(self, patch_llm):
        captured = {}

        def _capture(pv):
            from tests.conftest import prompt_text

            captured["text"] = prompt_text(pv)
            return NoveltyReport(verdicts=[])

        patch_llm(nc, _capture)

        state = {
            "summarized": [{"url": "https://a.com", "title": "A", "summary": "sa"}],
            "recent_history": [
                {"id": 7, "run_date": "2026-08-10", "title": "Old title", "topic_cluster": "X"}
            ],
        }
        nc.novelty_check(state)
        assert "Old title" in captured["text"]
        assert "id=7" in captured["text"]

    def test_format_history_empty_list_direct(self):
        # Inatteignable depuis novelty_check() (court-circuite avant l'appel),
        # mais _format_history reste testable directement pour son propre contrat.
        assert nc._format_history([]) == "(aucun article dans l'historique)"
