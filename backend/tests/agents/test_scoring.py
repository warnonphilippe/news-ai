"""Tests de src.agents.scoring — coeur du classement des articles."""

from datetime import date

import pytest

from src.agents import scoring

REF = date(2026, 8, 14)


# --------------------------------------------------------- parse_published

class TestParsePublished:
    def test_none_returns_none(self):
        assert scoring.parse_published(None) is None

    def test_empty_string_returns_none(self):
        assert scoring.parse_published("") is None

    @pytest.mark.parametrize("value", ["N/A", "n/a", "None", "NULL", "-", "  N/A  "])
    def test_placeholder_values_return_none(self, value):
        assert scoring.parse_published(value) is None

    def test_garbage_returns_none(self):
        assert scoring.parse_published("not a date at all") is None

    def test_iso_datetime_with_z(self):
        assert scoring.parse_published("2026-08-13T00:00:00.000Z") == date(2026, 8, 13)

    def test_iso_datetime_with_offset(self):
        assert scoring.parse_published("2026-08-13T10:00:00+02:00") == date(2026, 8, 13)

    def test_plain_iso_date(self):
        assert scoring.parse_published("2026-08-13") == date(2026, 8, 13)

    def test_iso_prefix_with_trailing_garbage(self):
        # Le fallback regex ISO_PREFIX doit s'appliquer sur un prefixe date valide.
        assert scoring.parse_published("2026-08-13 something weird") == date(2026, 8, 13)

    def test_invalid_calendar_date_in_prefix_returns_none(self):
        assert scoring.parse_published("2026-13-99") is None

    @pytest.mark.parametrize(
        "text,expected_days_ago",
        [
            ("3 days ago", 3),
            ("1 day ago", 1),
            ("2 weeks ago", 14),
            ("1 week ago", 7),
            ("6 months ago", 180),
            ("1 year ago", 365),
        ],
    )
    def test_relative_ages(self, text, expected_days_ago):
        from datetime import timedelta

        result = scoring.parse_published(text, today=REF)
        assert result == REF - timedelta(days=expected_days_ago)

    def test_relative_hours_and_minutes_treated_as_today(self):
        assert scoring.parse_published("5 hours ago", today=REF) == REF
        assert scoring.parse_published("30 minutes ago", today=REF) == REF

    def test_relative_defaults_to_real_today_when_not_given(self):
        # Sans `today`, la fonction retombe sur date.today() — on verifie juste
        # qu'elle ne plante pas et renvoie une date valide.
        result = scoring.parse_published("2 days ago")
        assert isinstance(result, date)

    def test_non_string_input_int(self):
        # str(value) doit gerer un type inattendu sans lever.
        assert scoring.parse_published(12345) is None


# ------------------------------------------------------------- age_in_days

class TestAgeInDays:
    def test_known_date(self):
        assert scoring.age_in_days("2026-08-10", REF) == 4

    def test_unknown_date_returns_none(self):
        assert scoring.age_in_days("N/A", REF) is None
        assert scoring.age_in_days(None, REF) is None

    def test_same_day_is_zero(self):
        assert scoring.age_in_days("2026-08-14", REF) == 0

    def test_future_date_clamped_to_zero(self):
        # Horloge/fuseau decale : une date "future" ne doit jamais donner un age negatif.
        assert scoring.age_in_days("2026-08-20", REF) == 0


# --------------------------------------------------------- freshness_factor

class TestFreshnessFactor:
    def test_unknown_age_uses_settings_default(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "undated_freshness_factor", 0.42)
        assert scoring.freshness_factor(None, 7) == 0.42

    def test_today_is_full_score(self):
        assert scoring.freshness_factor(0, 7) == 1.0

    def test_one_day_is_full_score(self):
        assert scoring.freshness_factor(1, 7) == 1.0

    def test_at_window_boundary(self):
        # age == window : encore dans la fenetre, valeur plancher de la decroissance lineaire.
        assert scoring.freshness_factor(7, 7) == pytest.approx(0.6)

    def test_mid_window_linear(self):
        # window=7 : span=6, age=4 -> 1.0 - 0.4*(4-1)/6 = 1.0 - 0.2 = 0.8
        assert scoring.freshness_factor(4, 7) == pytest.approx(0.8)

    def test_just_past_window(self):
        assert scoring.freshness_factor(8, 7) == pytest.approx(0.55)

    def test_far_past_window_floors_at_quarter(self):
        assert scoring.freshness_factor(1000, 7) == 0.25

    def test_never_below_floor(self):
        for age in (7, 50, 500, 5000):
            assert scoring.freshness_factor(age, 7) >= 0.25

    def test_window_of_one_day_span_guard(self):
        # window_days=1 : span = max(1-1, 1) = 1, evite une division par zero.
        result = scoring.freshness_factor(1, 1)
        assert result == 1.0  # age<=1 court-circuite avant le calcul de span


# ----------------------------------------------------------- source_factor

class TestSourceFactor:
    @pytest.fixture(autouse=True)
    def _weights_file(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        weights_file = tmp_path / "source_weights.yaml"
        weights_file.write_text(
            "default_factor: 1.0\n"
            "weights:\n"
            "  anthropic.com: 1.25\n"
            "  jetbrains.com: 1.15\n"
            "  medium.com: 0.85\n"
        )
        monkeypatch.setattr(settings, "source_weights_file", weights_file)

    def test_exact_match(self):
        assert scoring.source_factor("anthropic.com") == 1.25

    def test_suffix_match_subdomain(self):
        assert scoring.source_factor("blog.jetbrains.com") == 1.15

    def test_deep_subdomain_suffix_match(self):
        assert scoring.source_factor("a.b.jetbrains.com") == 1.15

    def test_www_prefix_stripped(self):
        assert scoring.source_factor("www.medium.com") == 0.85

    def test_case_insensitive(self):
        assert scoring.source_factor("ANTHROPIC.COM") == 1.25

    def test_unknown_domain_returns_default(self):
        assert scoring.source_factor("totally-unknown-domain.xyz") == 1.0

    def test_empty_source_returns_default(self):
        assert scoring.source_factor("") == 1.0

    def test_lookalike_domain_not_matched_as_suffix(self):
        # 'notjetbrains.com' ne doit PAS matcher 'jetbrains.com' (pas de '.' avant).
        assert scoring.source_factor("notjetbrains.com") == 1.0

    def test_missing_weights_file_returns_neutral(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "source_weights_file", tmp_path / "absent.yaml")
        scoring._source_weights.cache_clear()
        assert scoring.source_factor("anything.com") == 1.0

    def test_malformed_yaml_non_dict_returns_neutral(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        f = tmp_path / "weird.yaml"
        f.write_text("- just\n- a\n- list\n")
        monkeypatch.setattr(settings, "source_weights_file", f)
        scoring._source_weights.cache_clear()
        assert scoring.source_factor("anything.com") == 1.0

    def test_custom_default_factor(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        f = tmp_path / "custom_default.yaml"
        f.write_text("default_factor: 0.5\nweights:\n  known.com: 2.0\n")
        monkeypatch.setattr(settings, "source_weights_file", f)
        scoring._source_weights.cache_clear()
        assert scoring.source_factor("unknown.com") == 0.5
        assert scoring.source_factor("known.com") == 2.0


# ------------------------------------------------------------ compute_score

class TestComputeScore:
    def test_full_happy_path(self):
        article = {
            "relevance": 80,
            "published_date": "2026-08-13",
            "source": "unknown.example",
        }
        result = scoring.compute_score(article, REF, window_days=7)
        assert result["relevance"] == 80
        assert result["age_days"] == 1
        assert result["freshness_factor"] == 1.0
        assert result["source_factor"] == 1.0
        assert result["community_factor"] == 1.0
        assert result["final_score"] == 80.0

    def test_missing_relevance_defaults_to_zero(self):
        result = scoring.compute_score({"source": ""}, REF, 7)
        assert result["relevance"] == 0
        assert result["final_score"] == 0.0

    def test_non_numeric_relevance_defaults_to_zero(self):
        result = scoring.compute_score({"relevance": "not-a-number"}, REF, 7)
        assert result["relevance"] == 0

    def test_none_relevance_defaults_to_zero(self):
        result = scoring.compute_score({"relevance": None}, REF, 7)
        assert result["relevance"] == 0

    def test_precomputed_age_days_is_reused_not_recalculated(self):
        # age_days deja present dans l'article (pose par filter_recent) : on ne
        # doit pas re-parser published_date.
        article = {"relevance": 50, "age_days": 999, "published_date": "2026-08-14"}
        result = scoring.compute_score(article, REF, 7)
        assert result["age_days"] == 999

    def test_age_days_explicitly_none_falls_back_to_parsing(self):
        article = {"relevance": 50, "age_days": None, "published_date": "2026-08-13"}
        result = scoring.compute_score(article, REF, 7)
        assert result["age_days"] == 1

    def test_community_factor_present_is_used(self):
        # Sans published_date, l'age est inconnu -> freshness = undated_freshness_factor (0.75).
        result = scoring.compute_score(
            {"relevance": 100, "community_factor": 1.2, "published_date": "2026-08-13"}, REF, 7
        )
        assert result["community_factor"] == 1.2
        assert result["final_score"] == pytest.approx(100 * 1.0 * 1.0 * 1.2)

    def test_community_factor_zero_treated_as_absent(self):
        # `float(article.get("community_factor") or 1.0)` : 0 est falsy -> neutre.
        result = scoring.compute_score(
            {"relevance": 100, "community_factor": 0}, REF, 7
        )
        assert result["community_factor"] == 1.0

    def test_score_is_multiplicative_and_can_exceed_100(self):
        article = {"relevance": 95, "published_date": "2026-08-14", "community_factor": 1.2}
        result = scoring.compute_score(article, REF, 7)
        assert result["final_score"] > 100

    def test_final_score_rounded_to_two_decimals(self):
        article = {"relevance": 33, "age_days": 3, "community_factor": 1.111}
        result = scoring.compute_score(article, REF, 7)
        assert result["final_score"] == round(result["final_score"], 2)
