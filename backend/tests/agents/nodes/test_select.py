"""Tests du node select_top."""

from src.agents.nodes import select as sel


class TestSelectTop:
    def test_no_candidates_returns_empty_selected(self):
        result = sel.select_top({"run_date": "2026-08-14", "summarized": []})
        assert result["selected"] == []

    def test_missing_summarized_treated_as_empty(self):
        result = sel.select_top({"run_date": "2026-08-14"})
        assert result["selected"] == []

    def test_duplicates_are_excluded(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        state = {
            "run_date": "2026-08-14",
            "summarized": [
                {"url": "https://a.com", "novelty": "NEW", "relevance": 80, "source": ""},
                {"url": "https://b.com", "novelty": "DUPLICATE", "relevance": 99, "source": ""},
            ],
        }
        result = sel.select_top(state)
        urls = {a["url"] for a in result["selected"]}
        assert urls == {"https://a.com"}

    def test_sorted_by_final_score_descending(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        monkeypatch.setattr(settings, "search_window_days", 7)
        state = {
            "run_date": "2026-08-14",
            "summarized": [
                {
                    "url": "https://low.com",
                    "novelty": "NEW",
                    "relevance": 30,
                    "source": "",
                    "published_date": "2026-08-14",
                },
                {
                    "url": "https://high.com",
                    "novelty": "NEW",
                    "relevance": 90,
                    "source": "",
                    "published_date": "2026-08-14",
                },
            ],
        }
        result = sel.select_top(state)
        assert [a["url"] for a in result["selected"]] == [
            "https://high.com",
            "https://low.com",
        ]

    def test_truncated_to_max_articles_default(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 2)
        monkeypatch.setattr(settings, "search_window_days", 7)
        state = {
            "run_date": "2026-08-14",
            "summarized": [
                {
                    "url": f"https://a.com/{i}",
                    "novelty": "NEW",
                    "relevance": 50 + i,
                    "source": "",
                    "published_date": "2026-08-14",
                }
                for i in range(5)
            ],
        }
        result = sel.select_top(state)
        assert len(result["selected"]) == 2

    def test_state_max_articles_overrides_settings(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 2)
        monkeypatch.setattr(settings, "search_window_days", 7)
        state = {
            "run_date": "2026-08-14",
            "max_articles": 4,
            "summarized": [
                {
                    "url": f"https://a.com/{i}",
                    "novelty": "NEW",
                    "relevance": 50 + i,
                    "source": "",
                    "published_date": "2026-08-14",
                }
                for i in range(5)
            ],
        }
        result = sel.select_top(state)
        assert len(result["selected"]) == 4

    def test_score_components_attached_to_selected(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        monkeypatch.setattr(settings, "search_window_days", 7)
        state = {
            "run_date": "2026-08-14",
            "summarized": [
                {
                    "url": "https://a.com",
                    "novelty": "NEW",
                    "relevance": 80,
                    "source": "",
                    "published_date": "2026-08-14",
                }
            ],
        }
        result = sel.select_top(state)
        art = result["selected"][0]
        for key in (
            "relevance",
            "age_days",
            "freshness_factor",
            "source_factor",
            "community_factor",
            "final_score",
        ):
            assert key in art

    def test_state_window_used_for_scoring(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        monkeypatch.setattr(settings, "search_window_days", 999)  # tres large si utilise a tort
        state = {
            "run_date": "2026-08-14",
            "search_window_days": 7,  # override plus strict
            "summarized": [
                {
                    "url": "https://a.com",
                    "novelty": "NEW",
                    "relevance": 100,
                    "source": "",
                    "published_date": "2026-07-01",  # tres vieux relatif a la fenetre de 7j
                }
            ],
        }
        result = sel.select_top(state)
        # Avec une fenetre de 7j, cet article tres vieux doit subir le plancher de decote (0.25).
        assert result["selected"][0]["freshness_factor"] == 0.25
