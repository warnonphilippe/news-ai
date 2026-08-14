"""Initialisation du LLM (Azure OpenAI) et chargement des prompts."""

import logging

from langchain_openai import AzureChatOpenAI

from src.config.settings import ASSETS_DIR, settings

logger = logging.getLogger(__name__)


def get_llm(temperature: float | None = None) -> AzureChatOpenAI:
    """Cree une instance de chat Azure OpenAI configuree via .env.

    Note : certains deploiements (ex. gpt-5-chat) n'acceptent QUE la temperature
    par defaut ; on ne transmet donc `temperature` que si explicitement fournie.
    """
    kwargs = dict(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_chat_deployment,
        api_version=settings.azure_openai_api_version,
        api_key=settings.azure_openai_api_key,
        model_name=settings.azure_openai_chat_deployment,
        timeout=settings.llm_timeout,
    )
    if temperature is not None:
        kwargs["temperature"] = temperature
    return AzureChatOpenAI(**kwargs)


def load_prompt(filename: str) -> str:
    """Charge un prompt depuis src/assets."""
    path = ASSETS_DIR / filename
    return path.read_text(encoding="utf-8")
