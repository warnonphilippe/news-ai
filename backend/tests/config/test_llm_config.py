"""Tests de src.config.llm_config."""

from src.config import llm_config


class _FakeAzureChatOpenAI:
    """Capture les kwargs passes au constructeur, sans instancier de vrai client."""

    last_kwargs = None

    def __init__(self, **kwargs):
        _FakeAzureChatOpenAI.last_kwargs = kwargs


class TestGetLlm:
    def test_wires_settings_into_kwargs(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "azure_openai_endpoint", "https://ep.example/")
        monkeypatch.setattr(settings, "azure_openai_chat_deployment", "my-deployment")
        monkeypatch.setattr(settings, "azure_openai_api_version", "2099-01-01")
        monkeypatch.setattr(settings, "azure_openai_api_key", "secret-key")
        monkeypatch.setattr(settings, "llm_timeout", 99)
        monkeypatch.setattr(llm_config, "AzureChatOpenAI", _FakeAzureChatOpenAI)

        llm_config.get_llm()

        kwargs = _FakeAzureChatOpenAI.last_kwargs
        assert kwargs["azure_endpoint"] == "https://ep.example/"
        assert kwargs["azure_deployment"] == "my-deployment"
        assert kwargs["api_version"] == "2099-01-01"
        assert kwargs["api_key"] == "secret-key"
        assert kwargs["model_name"] == "my-deployment"
        assert kwargs["timeout"] == 99

    def test_temperature_omitted_by_default(self, monkeypatch):
        monkeypatch.setattr(llm_config, "AzureChatOpenAI", _FakeAzureChatOpenAI)
        llm_config.get_llm()
        assert "temperature" not in _FakeAzureChatOpenAI.last_kwargs

    def test_temperature_included_when_explicitly_given(self, monkeypatch):
        monkeypatch.setattr(llm_config, "AzureChatOpenAI", _FakeAzureChatOpenAI)
        llm_config.get_llm(temperature=0.3)
        assert _FakeAzureChatOpenAI.last_kwargs["temperature"] == 0.3

    def test_temperature_zero_is_included_not_treated_as_falsy(self, monkeypatch):
        # 0.0 est une temperature valide et doit etre transmise (piege `if temperature:`).
        monkeypatch.setattr(llm_config, "AzureChatOpenAI", _FakeAzureChatOpenAI)
        llm_config.get_llm(temperature=0.0)
        assert _FakeAzureChatOpenAI.last_kwargs["temperature"] == 0.0


class TestLoadPrompt:
    def test_reads_existing_prompt_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(llm_config, "ASSETS_DIR", tmp_path)
        (tmp_path / "greeting.md").write_text("Bonjour le test.")
        assert llm_config.load_prompt("greeting.md") == "Bonjour le test."

    def test_missing_file_raises(self, tmp_path, monkeypatch):
        import pytest

        monkeypatch.setattr(llm_config, "ASSETS_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            llm_config.load_prompt("absent.md")
