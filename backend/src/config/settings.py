"""Configuration de l'application, chargee depuis le fichier .env."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DATA_DIR = BACKEND_ROOT / "data"


class Settings(BaseSettings):
    """Parametres charges depuis les variables d'environnement / .env."""

    # --- Azure OpenAI ---
    azure_openai_endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    azure_openai_api_key: str = Field(..., description="Azure OpenAI API key")
    azure_openai_chat_deployment: str = Field(default="gpt-5-chat")
    azure_openai_api_version: str = Field(default="2025-01-01-preview")

    # --- Recherche ---
    exa_api_key: Optional[str] = Field(default=None)
    brave_api_key: Optional[str] = Field(default=None)

    # --- Runtime ---
    max_articles_per_day: int = Field(default=5)
    history_days: int = Field(default=14)
    search_window_days: int = Field(
        default=7, description="Fenetre de fraicheur : age max d'un article, en jours"
    )
    mcp_timeout: int = Field(default=60)

    # --- Scoring ---
    undated_freshness_factor: float = Field(
        default=0.75,
        description="Facteur applique aux articles sans date de publication exploitable",
    )

    # --- Chemins ---
    db_path: Path = Field(default=DATA_DIR / "news.db")
    tags_file: Path = Field(default=ASSETS_DIR / "tags.txt")
    seed_queries_file: Path = Field(default=ASSETS_DIR / "seed_queries.yaml")
    source_weights_file: Path = Field(default=ASSETS_DIR / "source_weights.yaml")

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
