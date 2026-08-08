"""Acces aux serveurs MCP de recherche (Exa + Brave) via le python-sdk mcp.

Chaque appel ouvre une session stdio courte (npx lance le serveur MCP a la
demande). Les erreurs (reseau, npx indisponible, cle manquante) sont capturees
et remontees sous forme de liste vide + message, pour que le pipeline degrade
proprement au lieu de planter.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.agents.search_parse import parse_mcp_text
from src.config.settings import settings

logger = logging.getLogger(__name__)


async def _call_mcp_tool(
    server_params: StdioServerParameters,
    preferred_tools: List[str],
    arguments_for: Dict[str, Any],
    provider: str,
) -> List[Dict[str, Any]]:
    """Ouvre une session MCP, choisit un tool, l'appelle et parse le resultat."""
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]

            tool_name = next((t for t in preferred_tools if t in names), None)
            if tool_name is None:
                tool_name = names[0] if names else None
            if tool_name is None:
                logger.warning("[%s] aucun tool MCP disponible", provider)
                return []

            result = await session.call_tool(tool_name, arguments=arguments_for)

            articles: List[Dict[str, Any]] = []
            for content in result.content or []:
                if getattr(content, "type", None) == "text":
                    articles.extend(parse_mcp_text(content.text, provider))
            return articles


async def _run_with_timeout(coro, provider: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Execute une coroutine de recherche avec timeout + capture d'erreur."""
    try:
        articles = await asyncio.wait_for(coro, timeout=settings.mcp_timeout)
        logger.info("[%s] %d resultats", provider, len(articles))
        return articles, []
    except asyncio.TimeoutError:
        msg = f"{provider}: timeout apres {settings.mcp_timeout}s"
        logger.warning(msg)
        return [], [msg]
    except Exception as exc:  # noqa: BLE001 — degradation volontaire
        msg = f"{provider}: {type(exc).__name__}: {exc}"
        logger.warning(msg)
        return [], [msg]


async def search_exa(query: str, num_results: int = 8) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Recherche semantique via le serveur MCP Exa (mcp-remote)."""
    if not settings.exa_api_key:
        return [], ["exa: cle EXA_API_KEY absente"]

    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "mcp-remote",
            f"https://mcp.exa.ai/mcp?exaApiKey={settings.exa_api_key}",
        ],
        env=os.environ.copy(),
    )
    coro = _call_mcp_tool(
        server_params,
        preferred_tools=["web_search_exa", "search"],
        arguments_for={"query": query, "numResults": num_results},
        provider="exa",
    )
    return await _run_with_timeout(coro, "exa")


async def search_brave(query: str, count: int = 8) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Recherche web complementaire via le serveur MCP Brave."""
    if not settings.brave_api_key:
        return [], ["brave: cle BRAVE_API_KEY absente"]

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env={**os.environ.copy(), "BRAVE_API_KEY": settings.brave_api_key},
    )
    coro = _call_mcp_tool(
        server_params,
        preferred_tools=["brave_web_search"],
        arguments_for={"query": query, "count": count},
        provider="brave",
    )
    return await _run_with_timeout(coro, "brave")
