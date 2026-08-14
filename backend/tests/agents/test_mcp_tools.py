"""Tests de src.agents.mcp_tools.

Le protocole MCP bas niveau (stdio_client/ClientSession reels) n'est pas
re-simule ici (deja verifie manuellement avec de vrais serveurs MCP durant le
developpement) ; ces tests couvrent la logique ecrite dans ce module : garde
des cles API, selection de tool, extraction du texte, et gestion des erreurs
(timeout, exception generique).
"""

import asyncio

import pytest

from src.agents import mcp_tools as mt

pytestmark = pytest.mark.asyncio


class _FakeAsyncCM:
    """Gestionnaire de contexte async minimal, retourne `value` a l'entree."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *exc):
        return False


class _FakeContent:
    def __init__(self, text):
        self.text = text
        self.type = "text"


class _FakeToolsList:
    def __init__(self, names):
        self.tools = [type("T", (), {"name": n})() for n in names]


class _FakeSession:
    """Remplace ClientSession pour tester _call_mcp_tool sans reseau/subprocess."""

    def __init__(self, tool_names, call_result_text):
        self._tool_names = tool_names
        self._call_result_text = call_result_text
        self.called_with = None

    async def initialize(self):
        pass

    async def list_tools(self):
        return _FakeToolsList(self._tool_names)

    async def call_tool(self, name, arguments):
        self.called_with = (name, arguments)
        content = [_FakeContent(self._call_result_text)] if self._call_result_text else []
        return type("Result", (), {"content": content})()


def _patch_mcp_layer(monkeypatch, session):
    monkeypatch.setattr(mt, "stdio_client", lambda params: _FakeAsyncCM((None, None)))
    monkeypatch.setattr(mt, "ClientSession", lambda read, write: _FakeAsyncCM(session))


class TestCallMcpTool:
    async def test_prefers_first_matching_tool(self, monkeypatch):
        session = _FakeSession(
            tool_names=["other_tool", "web_search_exa"],
            call_result_text="Title: T\nURL: https://a.com\n",
        )
        _patch_mcp_layer(monkeypatch, session)

        result = await mt._call_mcp_tool(
            server_params=object(),
            preferred_tools=["web_search_exa", "search"],
            arguments_for={"query": "q"},
            provider="exa",
        )
        assert session.called_with[0] == "web_search_exa"
        assert result[0]["title"] == "T"

    async def test_falls_back_to_first_tool_when_no_preferred_match(self, monkeypatch):
        session = _FakeSession(
            tool_names=["only_tool"], call_result_text="Title: T\nURL: https://a.com\n"
        )
        _patch_mcp_layer(monkeypatch, session)

        result = await mt._call_mcp_tool(
            server_params=object(),
            preferred_tools=["web_search_exa"],
            arguments_for={"query": "q"},
            provider="exa",
        )
        assert session.called_with[0] == "only_tool"
        assert len(result) == 1

    async def test_no_tools_available_returns_empty(self, monkeypatch):
        session = _FakeSession(tool_names=[], call_result_text="")
        _patch_mcp_layer(monkeypatch, session)

        result = await mt._call_mcp_tool(
            server_params=object(),
            preferred_tools=["web_search_exa"],
            arguments_for={},
            provider="exa",
        )
        assert result == []
        assert session.called_with is None  # call_tool jamais invoque

    async def test_non_text_content_ignored(self, monkeypatch):
        session = _FakeSession(tool_names=["t"], call_result_text="")
        _patch_mcp_layer(monkeypatch, session)

        async def _call_tool(name, arguments):
            session.called_with = (name, arguments)
            binary_content = type("C", (), {"type": "binary", "text": "ignored"})()
            return type("Result", (), {"content": [binary_content]})()

        session.call_tool = _call_tool
        result = await mt._call_mcp_tool(
            server_params=object(), preferred_tools=["t"], arguments_for={}, provider="exa"
        )
        assert result == []


class TestRunWithTimeout:
    async def test_success_passes_through(self):
        # La coroutine resout vers la liste d'articles seule ; _run_with_timeout
        # construit lui-meme le tuple (articles, errors) autour du resultat.
        async def _ok():
            return ["article"]

        result, errors = await mt._run_with_timeout(_ok(), "exa")
        assert result == ["article"]
        assert errors == []

    async def test_timeout_returns_empty_with_message(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "mcp_timeout", 0.01)

        async def _slow():
            await asyncio.sleep(1)
            return []

        result, errors = await mt._run_with_timeout(_slow(), "exa")
        assert result == []
        assert "timeout" in errors[0]

    async def test_generic_exception_captured(self):
        async def _boom():
            raise ValueError("network down")

        result, errors = await mt._run_with_timeout(_boom(), "brave")
        assert result == []
        assert "brave" in errors[0]
        assert "ValueError" in errors[0]


class TestSearchExa:
    async def test_missing_api_key_returns_error_without_calling_mcp(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "exa_api_key", None)
        result, errors = await mt.search_exa("query")
        assert result == []
        assert "EXA_API_KEY" in errors[0]

    async def test_start_published_date_included_when_given(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "exa_api_key", "key")
        captured = {}

        async def _fake_call_mcp_tool(server_params, preferred_tools, arguments_for, provider):
            captured["arguments"] = arguments_for
            return []

        monkeypatch.setattr(mt, "_call_mcp_tool", _fake_call_mcp_tool)
        await mt.search_exa("query", start_published_date="2026-08-01")
        assert captured["arguments"]["startPublishedDate"] == "2026-08-01"

    async def test_no_start_published_date_key_when_omitted(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "exa_api_key", "key")
        captured = {}

        async def _fake_call_mcp_tool(server_params, preferred_tools, arguments_for, provider):
            captured["arguments"] = arguments_for
            return []

        monkeypatch.setattr(mt, "_call_mcp_tool", _fake_call_mcp_tool)
        await mt.search_exa("query")
        assert "startPublishedDate" not in captured["arguments"]

    async def test_num_results_passed_through(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "exa_api_key", "key")
        captured = {}

        async def _fake_call_mcp_tool(server_params, preferred_tools, arguments_for, provider):
            captured["arguments"] = arguments_for
            return []

        monkeypatch.setattr(mt, "_call_mcp_tool", _fake_call_mcp_tool)
        await mt.search_exa("query", num_results=3)
        assert captured["arguments"]["numResults"] == 3


class TestSearchBrave:
    async def test_missing_api_key_returns_error_without_calling_mcp(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "brave_api_key", None)
        result, errors = await mt.search_brave("query")
        assert result == []
        assert "BRAVE_API_KEY" in errors[0]

    async def test_passes_count_argument(self, monkeypatch):
        from src.config.settings import settings

        monkeypatch.setattr(settings, "brave_api_key", "key")
        captured = {}

        async def _fake_call_mcp_tool(server_params, preferred_tools, arguments_for, provider):
            captured["arguments"] = arguments_for
            return []

        monkeypatch.setattr(mt, "_call_mcp_tool", _fake_call_mcp_tool)
        await mt.search_brave("query", count=3)
        assert captured["arguments"]["count"] == 3
