"""Tests de src.agents.community — signal Hacker News."""

import math

import httpx
import pytest

from src.agents import community


# ------------------------------------------------------------ community_factor

class TestCommunityFactor:
    @pytest.mark.parametrize("points", [None, 0, -5])
    def test_no_or_invalid_signal_is_neutral(self, points):
        assert community.community_factor(points) == 1.0

    def test_known_value_matches_formula(self):
        points = 100
        expected = round(1.0 + min(0.20, 0.05 * math.log10(1 + points)), 3)
        assert community.community_factor(points) == expected

    def test_small_positive_gives_small_bonus(self):
        result = community.community_factor(2)
        assert 1.0 < result < 1.05

    def test_capped_at_max_bonus(self):
        result = community.community_factor(10_000_000)
        assert result == 1.20

    def test_monotonic_increase(self):
        vals = [community.community_factor(p) for p in (1, 10, 100, 1000, 10000)]
        assert vals == sorted(vals)


# --------------------------------------------------------- enrich_with_community

class _FakeResponse:
    def __init__(self, hits):
        self._hits = hits

    def raise_for_status(self):
        pass

    def json(self):
        return {"hits": self._hits}


class _FakeAsyncClient:
    """Remplace httpx.AsyncClient pour controler les reponses HN sans reseau."""

    def __init__(self, responses_by_url, raise_for=None):
        self._responses_by_url = responses_by_url
        self._raise_for = raise_for or set()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, _endpoint, params):
        url = params["query"]
        if url in self._raise_for:
            raise httpx.ConnectError("boom")
        return _FakeResponse(self._responses_by_url.get(url, []))


class TestEnrichWithCommunity:
    def test_disabled_signal_skips_network_entirely(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "enable_hn_signal", False)
        articles = [{"url": "https://a.com"}, {"url": "https://b.com"}]
        community.enrich_with_community(articles)
        assert all(a["community_factor"] == 1.0 for a in articles)
        assert all("hn_points" not in a for a in articles)

    def test_empty_list_is_a_noop(self):
        community.enrich_with_community([])  # ne doit pas lever

    def test_article_with_hits_gets_points_and_factor(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "enable_hn_signal", True)
        fake_client = _FakeAsyncClient(
            {"https://a.com": [{"points": 150, "num_comments": 30}]}
        )
        monkeypatch.setattr(community.httpx, "AsyncClient", lambda **kw: fake_client)

        articles = [{"url": "https://a.com"}]
        community.enrich_with_community(articles)

        assert articles[0]["hn_points"] == 150
        assert articles[0]["hn_comments"] == 30
        assert articles[0]["community_factor"] == community.community_factor(150)

    def test_article_without_hits_stays_neutral(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "enable_hn_signal", True)
        fake_client = _FakeAsyncClient({"https://a.com": []})
        monkeypatch.setattr(community.httpx, "AsyncClient", lambda **kw: fake_client)

        articles = [{"url": "https://a.com"}]
        community.enrich_with_community(articles)

        assert articles[0]["hn_points"] is None
        assert articles[0]["hn_comments"] is None
        assert articles[0]["community_factor"] == 1.0

    def test_multiple_hits_keeps_best_reception(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "enable_hn_signal", True)
        fake_client = _FakeAsyncClient(
            {
                "https://a.com": [
                    {"points": 10, "num_comments": 2},
                    {"points": 500, "num_comments": 100},
                    {"points": 50, "num_comments": 5},
                ]
            }
        )
        monkeypatch.setattr(community.httpx, "AsyncClient", lambda **kw: fake_client)

        articles = [{"url": "https://a.com"}]
        community.enrich_with_community(articles)
        assert articles[0]["hn_points"] == 500

    def test_network_error_on_one_article_degrades_to_neutral_for_it_only(
        self, monkeypatch
    ):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "enable_hn_signal", True)
        fake_client = _FakeAsyncClient(
            {"https://ok.com": [{"points": 42, "num_comments": 1}]},
            raise_for={"https://bad.com"},
        )
        monkeypatch.setattr(community.httpx, "AsyncClient", lambda **kw: fake_client)

        articles = [{"url": "https://ok.com"}, {"url": "https://bad.com"}]
        community.enrich_with_community(articles)

        assert articles[0]["hn_points"] == 42
        assert articles[1]["hn_points"] is None
        assert articles[1]["community_factor"] == 1.0

    def test_total_failure_falls_back_to_neutral_for_all(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "enable_hn_signal", True)

        def _boom(**kw):
            raise RuntimeError("network stack unavailable")

        monkeypatch.setattr(community.httpx, "AsyncClient", _boom)

        articles = [{"url": "https://a.com"}, {"url": "https://b.com"}]
        community.enrich_with_community(articles)

        assert all(a["community_factor"] == 1.0 for a in articles)

    def test_missing_url_key_treated_as_empty_string(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "enable_hn_signal", True)
        fake_client = _FakeAsyncClient({})
        monkeypatch.setattr(community.httpx, "AsyncClient", lambda **kw: fake_client)

        articles = [{}]  # pas de cle 'url'
        community.enrich_with_community(articles)
        assert articles[0]["community_factor"] == 1.0
