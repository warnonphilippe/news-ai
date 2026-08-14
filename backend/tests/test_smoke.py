"""Test de fumee : verifie que le harnais (conftest, imports src) fonctionne."""


def test_settings_import_with_dummy_env():
    from src.config.settings import settings

    assert settings.azure_openai_endpoint == "https://test.openai.azure.com/"
    assert settings.max_articles_per_day == 5


def test_repo_fixture_creates_isolated_db(repo, db_path):
    assert db_path.exists()
    assert repo.get_run("2026-01-01") is None
