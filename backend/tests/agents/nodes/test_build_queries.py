"""Tests du node build_queries (digest quotidien)."""

from src.agents.nodes.build_queries import build_queries


def _write_seed_file(path, content):
    path.write_text(content)


class TestBuildQueries:
    def test_combines_seed_axes_and_tag_query(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        seed = tmp_path / "seed.yaml"
        seed.write_text(
            "axis_one:\n  - 'query one'\n  - 'query two'\n"
            "axis_two:\n  - 'query three'\n"
        )
        monkeypatch.setattr(settings, "seed_queries_file", seed)

        state = {"tags": ["AI", "Java", "Python"]}
        result = build_queries(state)

        assert "query one" in result["queries"]
        assert "query two" in result["queries"]
        assert "query three" in result["queries"]
        assert any("AI, Java, Python" in q for q in result["queries"])

    def test_no_tags_means_no_extra_query(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        seed = tmp_path / "seed.yaml"
        seed.write_text("axis:\n  - 'only seed query'\n")
        monkeypatch.setattr(settings, "seed_queries_file", seed)

        result = build_queries({"tags": []})
        assert result["queries"] == ["only seed query"]

    def test_missing_tags_key_treated_as_empty(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        seed = tmp_path / "seed.yaml"
        seed.write_text("axis:\n  - 'q'\n")
        monkeypatch.setattr(settings, "seed_queries_file", seed)

        result = build_queries({})
        assert result["queries"] == ["q"]

    def test_tags_capped_at_six(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        seed = tmp_path / "seed.yaml"
        seed.write_text("axis: []\n")
        monkeypatch.setattr(settings, "seed_queries_file", seed)

        tags = [f"tag{i}" for i in range(10)]
        result = build_queries({"tags": tags})
        assert result["queries"] == [
            "latest news and releases about "
            + ", ".join(tags[:6])
            + " for developers"
        ]

    def test_missing_seed_file_falls_back_to_tag_query_only(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "seed_queries_file", tmp_path / "absent.yaml")
        result = build_queries({"tags": ["AI"]})
        assert len(result["queries"]) == 1
        assert "AI" in result["queries"][0]

    def test_duplicates_removed_preserving_order(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        seed = tmp_path / "seed.yaml"
        seed.write_text("axis:\n  - 'dup'\n  - 'dup'\n  - 'unique'\n")
        monkeypatch.setattr(settings, "seed_queries_file", seed)

        result = build_queries({"tags": []})
        assert result["queries"] == ["dup", "unique"]

    def test_non_list_axis_values_ignored(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        seed = tmp_path / "seed.yaml"
        seed.write_text("axis_ok:\n  - 'q1'\naxis_bad: 'not a list'\n")
        monkeypatch.setattr(settings, "seed_queries_file", seed)

        result = build_queries({"tags": []})
        assert result["queries"] == ["q1"]
