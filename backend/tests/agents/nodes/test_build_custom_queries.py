"""Tests du node build_custom_queries (recherche personnalisee)."""

from src.agents.nodes.build_custom_queries import build_custom_queries


class TestBuildCustomQueries:
    def test_produces_raw_and_scoped_variant(self):
        result = build_custom_queries({"custom_query": "RAG avec pgvector"})
        assert result["queries"] == [
            "RAG avec pgvector",
            "RAG avec pgvector for software developers",
        ]

    def test_empty_query_yields_no_queries(self):
        assert build_custom_queries({"custom_query": ""})["queries"] == []

    def test_missing_key_yields_no_queries(self):
        assert build_custom_queries({})["queries"] == []

    def test_whitespace_only_query_yields_no_queries(self):
        assert build_custom_queries({"custom_query": "   "})["queries"] == []

    def test_query_is_stripped(self):
        result = build_custom_queries({"custom_query": "  Kubernetes  "})
        assert result["queries"][0] == "Kubernetes"
