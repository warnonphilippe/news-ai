"""Tests des nodes load_config (quotidien) et load_config_custom."""

from src.agents.nodes.load_config import load_config_custom, make_load_config


class TestMakeLoadConfig:
    def test_loads_tags_and_history(self, repo, tmp_path, monkeypatch):
        from src.config.settings import settings

        tags_file = tmp_path / "tags.txt"
        tags_file.write_text("AI\nJava\n\nPython\n")
        monkeypatch.setattr(settings, "tags_file", tags_file)
        monkeypatch.setattr(settings, "history_days", 14)

        load_config = make_load_config(repo)
        result = load_config({"run_date": "2026-08-14"})

        assert result["tags"] == ["AI", "Java", "Python"]
        assert result["recent_history"] == []
        assert result["errors"] == []

    def test_history_passed_before_run_date(self, repo, article_factory, tmp_path, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "tags_file", tmp_path / "absent.txt")
        monkeypatch.setattr(settings, "history_days", 14)

        repo.try_start_run("2026-08-10")
        repo.save_articles("2026-08-10", [article_factory()])

        load_config = make_load_config(repo)
        result = load_config({"run_date": "2026-08-14"})
        assert len(result["recent_history"]) == 1

    def test_missing_tags_file_yields_empty_list(self, repo, tmp_path, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "tags_file", tmp_path / "does-not-exist.txt")
        load_config = make_load_config(repo)
        result = load_config({"run_date": "2026-08-14"})
        assert result["tags"] == []

    def test_blank_lines_in_tags_file_ignored(self, tmp_path, monkeypatch, repo):
        from src.config.settings import settings

        tags_file = tmp_path / "tags.txt"
        tags_file.write_text("AI\n\n  \nJava\n")
        monkeypatch.setattr(settings, "tags_file", tags_file)
        load_config = make_load_config(repo)
        result = load_config({"run_date": "2026-08-14"})
        assert result["tags"] == ["AI", "Java"]


class TestLoadConfigCustom:
    def test_never_loads_history(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "tags_file", tmp_path / "absent.txt")
        result = load_config_custom({"run_date": "2026-08-14", "custom_query": "RAG"})
        assert result["recent_history"] == []

    def test_loads_tags_same_way_as_daily(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        tags_file = tmp_path / "tags.txt"
        tags_file.write_text("MCP\nAgents\n")
        monkeypatch.setattr(settings, "tags_file", tags_file)
        result = load_config_custom({"run_date": "2026-08-14"})
        assert result["tags"] == ["MCP", "Agents"]

    def test_errors_initialized_empty(self, tmp_path, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "tags_file", tmp_path / "absent.txt")
        result = load_config_custom({"run_date": "2026-08-14"})
        assert result["errors"] == []
