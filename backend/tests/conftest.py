"""Configuration globale des tests.

Fixe des variables d'environnement factices AVANT tout import de `src.*`,
pour que la suite soit hermetique :
  - ne depend jamais des vrais secrets d'un backend/.env local ;
  - fonctionne a l'identique sur un clone fraichement clone (CI) ;
  - ne touche jamais la vraie base backend/data/news.db.

Pydantic-settings applique la precedence : variables d'environnement OS >
fichier .env > valeurs par defaut. Fixer ces variables ici les fait donc
gagner sur un .env reel eventuellement present sur la machine du developpeur.
"""

import os
import tempfile
from pathlib import Path as _Path

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-azure-key")
os.environ.setdefault("EXA_API_KEY", "test-exa-key")
os.environ.setdefault("BRAVE_API_KEY", "test-brave-key")

# `src.api.routes` instancie `Repository(settings.db_path)` au niveau MODULE,
# des l'import — avant qu'un test ne puisse patcher quoi que ce soit. On
# redirige donc db_path vers un fichier temporaire de session ici, avant tout
# import de `src.*`, pour garantir qu'aucun import ne touche jamais la vraie
# base backend/data/news.db, meme un import isole sans fixture.
_session_tmp_db = _Path(tempfile.mkdtemp(prefix="ai-for-dev-tests-")) / "session.db"
os.environ.setdefault("DB_PATH", str(_session_tmp_db))

import shutil
from pathlib import Path
from typing import Any, Dict

import pytest

from src.db.repository import Repository


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Chemin de base SQLite temporaire, jamais la vraie base de l'app."""
    return tmp_path / "test.db"


@pytest.fixture
def repo(db_path: Path) -> Repository:
    """Repository sur une base SQLite temporaire et vide."""
    return Repository(db_path)


def make_article(**overrides: Any) -> Dict[str, Any]:
    """Fabrique un article candidat minimal, avec des surcharges au besoin."""
    base: Dict[str, Any] = {
        "url": "https://example.com/article",
        "normalized_url": "https://example.com/article",
        "title": "Titre de test",
        "summary": "Resume de test.",
        "why_it_matters": "Pourquoi ca compte.",
        "source": "example.com",
        "published_date": "2026-08-10",
        "tags": ["Test"],
        "topic_cluster": "Test",
        "links": [],
        "snippet": "Extrait de test.",
        "novelty": "NEW",
        "is_update_of": None,
        "relevance": 80,
        "relevance_rationale": "Pertinent.",
        "age_days": 2,
    }
    base.update(overrides)
    return base


@pytest.fixture
def article_factory():
    return make_article


@pytest.fixture(autouse=True)
def _isolate_source_weights_cache():
    """Vide le cache lru_cache de scoring._source_weights entre chaque test.

    Necessaire car plusieurs tests pointent settings.source_weights_file vers
    des fichiers temporaires differents ; sans ce nettoyage, le premier test
    execute figerait le resultat pour tous les suivants.
    """
    from src.agents import scoring

    scoring._source_weights.cache_clear()
    yield
    scoring._source_weights.cache_clear()


class FakeStructuredLLM:
    """Remplace `get_llm()` pour les tests de nodes qui font `prompt | get_llm()
    .with_structured_output(Model)`.

    `result_fn` recoit le `ChatPromptValue` rendu (permet de differencier le
    comportement par candidat en inspectant le texte du prompt, ex. via une
    marque presente dans son URL/titre) et doit renvoyer soit une instance du
    modele Pydantic attendu, soit une Exception a lever (simulant un echec LLM).
    """

    def __init__(self, result_fn):
        self._result_fn = result_fn

    def with_structured_output(self, _model):
        from langchain_core.runnables import RunnableLambda

        def _call(prompt_value):
            result = self._result_fn(prompt_value)
            if isinstance(result, Exception):
                raise result
            return result

        return RunnableLambda(_call)


def prompt_text(prompt_value) -> str:
    """Extrait le texte concatene d'un ChatPromptValue, pour y chercher un marqueur."""
    return " ".join(m.content for m in prompt_value.to_messages())


@pytest.fixture
def patch_llm(monkeypatch):
    """Retourne patch(module, result_fn) : remplace `module.get_llm` par un faux LLM."""

    def _patch(module, result_fn):
        monkeypatch.setattr(module, "get_llm", lambda *a, **kw: FakeStructuredLLM(result_fn))

    return _patch


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """Redirige tous les chemins de fichiers de settings vers un repertoire temporaire.

    Copie les vrais assets (tags, prompts, yaml) pour que les tests qui en ont
    besoin lisent un contenu realiste, sans jamais toucher ni dependre de l'etat
    du vrai repertoire backend/data ou d'un .env modifie en cours de route.
    """
    from src.config.settings import settings

    real_assets = Path(settings.tags_file).parent
    fake_assets = tmp_path / "assets"
    shutil.copytree(real_assets, fake_assets)

    monkeypatch.setattr(settings, "db_path", tmp_path / "news.db")
    monkeypatch.setattr(settings, "tags_file", fake_assets / "tags.txt")
    monkeypatch.setattr(settings, "seed_queries_file", fake_assets / "seed_queries.yaml")
    monkeypatch.setattr(settings, "source_weights_file", fake_assets / "source_weights.yaml")
    monkeypatch.setattr(settings, "relevance_prompt_file", fake_assets / "relevance_prompt.md")
    monkeypatch.setattr(
        settings, "custom_relevance_prompt_file", fake_assets / "custom_relevance_prompt.md"
    )
    return fake_assets
