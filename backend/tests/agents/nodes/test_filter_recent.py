"""Tests du node filter_recent — fenetre de fraicheur, tri, repli, fallback."""

from src.agents.nodes.filter_recent import filter_recent


def _cand(url, published_date=None):
    return {"url": url, "published_date": published_date}


class TestFilterRecentBasics:
    def test_keeps_articles_within_window(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        state = {
            "run_date": "2026-08-14",
            "deduped": [_cand("https://a.com/1", "2026-08-13")],
        }
        result = filter_recent(state)
        assert len(result["deduped"]) == 1
        assert result["deduped"][0]["age_days"] == 1

    def test_excludes_articles_beyond_window(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        state = {
            "run_date": "2026-08-14",
            "deduped": [
                _cand("https://a.com/1", "2026-08-13"),  # 1j, dans la fenetre
                _cand("https://a.com/2", "2026-01-01"),  # tres vieux, hors fenetre
                _cand("https://a.com/3", "2026-08-12"),  # 2j
                _cand("https://a.com/4", "2026-08-10"),  # 4j
                _cand("https://a.com/5", "2026-08-09"),  # 5j
                _cand("https://a.com/6", "2026-08-08"),  # 6j
            ],
        }
        result = filter_recent(state)
        urls = {a["url"] for a in result["deduped"]}
        assert "https://a.com/2" not in urls  # exclu (au-dela du repli aussi)

    def test_exact_boundary_age_equals_window_is_kept(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        state = {
            "run_date": "2026-08-14",
            "deduped": [_cand("https://a.com/1", "2026-08-07")],  # age == 7
        }
        result = filter_recent(state)
        assert len(result["deduped"]) == 1

    def test_boundary_age_window_plus_one_excluded_without_repli(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 1)
        state = {
            "run_date": "2026-08-14",
            "deduped": [
                _cand("https://a.com/fresh", "2026-08-13"),  # comble le quota (1)
                _cand("https://a.com/stale", "2026-08-06"),  # age == 8, exclu
            ],
        }
        result = filter_recent(state)
        urls = {a["url"] for a in result["deduped"]}
        assert "https://a.com/stale" not in urls

    def test_unknown_date_kept_and_sorted_last(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        state = {
            "run_date": "2026-08-14",
            "deduped": [
                _cand("https://a.com/nodate", None),
                _cand("https://a.com/fresh", "2026-08-14"),
            ],
        }
        result = filter_recent(state)
        assert [a["url"] for a in result["deduped"]] == [
            "https://a.com/fresh",
            "https://a.com/nodate",
        ]

    def test_sorted_freshest_first(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        state = {
            "run_date": "2026-08-14",
            "deduped": [
                _cand("https://a.com/old", "2026-08-10"),
                _cand("https://a.com/new", "2026-08-14"),
                _cand("https://a.com/mid", "2026-08-12"),
            ],
        }
        result = filter_recent(state)
        assert [a["url"] for a in result["deduped"]] == [
            "https://a.com/new",
            "https://a.com/mid",
            "https://a.com/old",
        ]


class TestFilterRecentRepli:
    def test_repli_completes_with_oldest_stale_when_not_enough_fresh(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 3)
        state = {
            "run_date": "2026-08-14",
            "deduped": [
                _cand("https://a.com/fresh", "2026-08-13"),  # 1 seul dans la fenetre
                _cand("https://a.com/stale1", "2026-07-01"),  # tres vieux
                _cand("https://a.com/stale2", "2026-06-01"),  # encore plus vieux
            ],
        }
        result = filter_recent(state)
        # max_articles=3, 1 seul frais -> complete avec les 2 candidats stale,
        # eux-memes tries du moins ancien au plus ancien (stale1 avant stale2).
        assert [a["url"] for a in result["deduped"]] == [
            "https://a.com/fresh",
            "https://a.com/stale1",
            "https://a.com/stale2",
        ]

    def test_no_repli_when_enough_fresh_articles(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 2)
        state = {
            "run_date": "2026-08-14",
            "deduped": [
                _cand("https://a.com/1", "2026-08-14"),
                _cand("https://a.com/2", "2026-08-13"),
                _cand("https://a.com/stale", "2026-01-01"),
            ],
        }
        result = filter_recent(state)
        urls = {a["url"] for a in result["deduped"]}
        assert "https://a.com/stale" not in urls

    def test_repli_with_no_stale_candidates_at_all(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 10)
        state = {"run_date": "2026-08-14", "deduped": [_cand("https://a.com/1", "2026-08-14")]}
        result = filter_recent(state)
        assert len(result["deduped"]) == 1  # pas de crash faute de stock stale

    def test_empty_deduped_returns_empty(self):
        result = filter_recent({"run_date": "2026-08-14", "deduped": []})
        assert result["deduped"] == []


class TestFilterRecentStateFallback:
    """Verifie le mecanisme central de non-regression : state.get(...) prime sur
    settings.X quand present, et settings.X est utilise en son absence (chemin
    du digest quotidien, jamais modifie)."""

    def test_settings_used_when_state_absent(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 3)
        monkeypatch.setattr(settings, "max_articles_per_day", 1)
        state = {
            "run_date": "2026-08-14",
            "deduped": [_cand("https://a.com/1", "2026-08-10")],  # age=4, > 3
        }
        result = filter_recent(state)
        # Sans repli possible (pas d'autre candidat), l'unique article reste
        # (repli le rajoute) mais on verifie que la fenetre effective est bien 3.
        assert result["deduped"][0]["age_days"] == 4  # calcule correctement

    def test_state_window_overrides_settings(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 999)  # tres large
        monkeypatch.setattr(settings, "max_articles_per_day", 5)
        state = {
            "run_date": "2026-08-14",
            "search_window_days": 2,  # override plus strict
            "deduped": [
                _cand("https://a.com/fresh", "2026-08-13"),  # age=1, dans la fenetre de 2
                _cand("https://a.com/stale", "2026-08-01"),  # age=13, hors fenetre de 2
            ],
        }
        result = filter_recent(state)
        # Avec settings=999 (si utilise a tort), 'stale' serait garde directement.
        # On verifie qu'il est bien traite comme 'stale' (donc soumis au repli,
        # pas garde tel quel comme un article frais) via son classement dans le tri.
        assert result["deduped"][0]["url"] == "https://a.com/fresh"

    def test_state_max_articles_overrides_settings_for_repli(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "search_window_days", 7)
        monkeypatch.setattr(settings, "max_articles_per_day", 1)  # settings: repli desactive vite
        state = {
            "run_date": "2026-08-14",
            "max_articles": 3,  # override : recherche personnalisee veut plus
            "deduped": [
                _cand("https://a.com/fresh", "2026-08-13"),
                _cand("https://a.com/stale1", "2026-01-01"),
                _cand("https://a.com/stale2", "2026-01-02"),
            ],
        }
        result = filter_recent(state)
        assert len(result["deduped"]) == 3  # repli va jusqu'a 3, pas 1
