"""Tests de src.config.settings.Settings — defauts et champs requis.

Note : ces tests construisent des instances `Settings(...)` independantes du
singleton module `settings` (jamais mute), pour ne pas interferer avec les
autres tests qui monkeypatchent ce singleton.

`conftest.py` injecte des cles Azure/Exa/Brave factices directement dans
`os.environ` (pas seulement dans un .env) pour que TOUT LE RESTE de la suite
fonctionne hors ligne. `_env_file=None` ne desactive que la lecture du fichier
.env, pas celle des variables d'environnement OS — les tests de "champ requis
absent" doivent donc explicitement retirer ces variables de l'environnement
pour la duree du test (monkeypatch.delenv les restaure automatiquement apres).
"""

import pytest
from pydantic import ValidationError

from src.config.settings import Settings


@pytest.fixture
def no_azure_env(monkeypatch):
    """Retire les cles Azure de l'environnement pour tester les champs requis."""
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)


class TestRequiredFields:
    def test_missing_azure_endpoint_raises(self, no_azure_env):
        with pytest.raises(ValidationError):
            Settings(azure_openai_api_key="k", _env_file=None)

    def test_missing_azure_api_key_raises(self, no_azure_env):
        with pytest.raises(ValidationError):
            Settings(azure_openai_endpoint="https://e/", _env_file=None)

    def test_both_required_fields_present_succeeds(self, no_azure_env):
        s = Settings(
            azure_openai_endpoint="https://e/", azure_openai_api_key="k", _env_file=None
        )
        assert s.azure_openai_endpoint == "https://e/"


class TestDefaults:
    @pytest.fixture
    def minimal_settings(self):
        return Settings(
            azure_openai_endpoint="https://e/", azure_openai_api_key="k", _env_file=None
        )

    def test_business_defaults(self, minimal_settings):
        assert minimal_settings.max_articles_per_day == 5
        assert minimal_settings.history_days == 14
        assert minimal_settings.search_window_days == 7

    def test_custom_search_defaults(self, minimal_settings):
        assert minimal_settings.custom_search_window_days == 30
        assert minimal_settings.custom_search_max_results == 10

    def test_scoring_defaults(self, minimal_settings):
        assert minimal_settings.undated_freshness_factor == 0.75
        assert minimal_settings.enable_hn_signal is True

    def test_timeout_defaults(self, minimal_settings):
        assert minimal_settings.mcp_timeout == 60
        assert minimal_settings.llm_timeout == 45
        assert minimal_settings.hn_timeout == 10

    def test_azure_deployment_default(self, minimal_settings):
        assert minimal_settings.azure_openai_chat_deployment == "gpt-5-chat"

    def test_optional_search_keys_default_to_none(self, monkeypatch):
        # EXA_API_KEY/BRAVE_API_KEY sont injectes par conftest pour le reste de
        # la suite : retires ici pour verifier le vrai defaut du champ.
        monkeypatch.delenv("EXA_API_KEY", raising=False)
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        s = Settings(
            azure_openai_endpoint="https://e/", azure_openai_api_key="k", _env_file=None
        )
        assert s.exa_api_key is None
        assert s.brave_api_key is None


class TestOverrides:
    def test_explicit_values_override_defaults(self):
        s = Settings(
            azure_openai_endpoint="https://e/",
            azure_openai_api_key="k",
            max_articles_per_day=99,
            _env_file=None,
        )
        assert s.max_articles_per_day == 99

    def test_case_insensitive_env_var_names(self, monkeypatch):
        # case_sensitive=False : une variable OS en majuscules alimente le champ.
        monkeypatch.setenv("MAX_ARTICLES_PER_DAY", "3")
        s = Settings(
            azure_openai_endpoint="https://e/", azure_openai_api_key="k", _env_file=None
        )
        assert s.max_articles_per_day == 3
