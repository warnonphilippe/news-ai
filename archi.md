# Architecture — IA for DEV

Ce document décrit l'architecture technique du projet : structure, briques
logicielles, bibliothèques et choix de conception. Pour les fonctionnalités et
le lancement, voir [README.md](README.md).

---

## 1. Vue d'ensemble

Application **locale mono-utilisateur** de veille quotidienne « IA for DEV ».
Deux processus démarrés ensemble par `start.sh` / `start.bat` :

```
┌──────────────────────┐        proxy /api         ┌───────────────────────────┐
│   Frontend Angular    │  ───────────────────────► │       Backend FastAPI      │
│   (ng serve / Vite)   │ ◄───────────────────────  │        (uvicorn)           │
│      :4200            │        JSON REST          │          :8000             │
└──────────────────────┘                            └────────────┬──────────────┘
                                                                  │
                                          ┌───────────────────────┼───────────────────────┐
                                          ▼                       ▼                       ▼
                                   ┌─────────────┐        ┌───────────────┐        ┌──────────────┐
                                   │  LangGraph  │        │  Azure OpenAI │        │ MCP servers   │
                                   │  pipeline   │ ─────► │  (gpt-5-chat) │        │ Exa + Brave   │
                                   └──────┬──────┘        └───────────────┘        │ (via npx)     │
                                          ▼                                         └──────────────┘
                                   ┌─────────────┐
                                   │   SQLite    │  (backend/data/news.db)
                                   └─────────────┘
```

- Le **backend** orchestre la recherche du jour via un graphe LangGraph, résume
  et dédoublonne via le LLM, persiste dans SQLite et expose une API REST.
- Le **frontend** consomme l'API (via un proxy `/api` en dev) et affiche le
  digest.
- Le lancement, le run du jour et l'ouverture du navigateur sont automatisés par
  les scripts + `run.py`.

---

## 2. Structure du dépôt

```
news/
├── start.sh / start.bat           # démarrage tout-en-un (mac-linux / windows)
├── run.py                         # launcher partagé (stdlib) : health + POST /run + navigateur
├── README.md / archi.md
├── .gitignore
│
├── backend/                       # === Python ===
│   ├── pyproject.toml             # dépendances (setuptools, editable install)
│   ├── .env.example               # gabarit committé
│   ├── .env                       # secrets (gitignoré)
│   ├── data/                      # news.db (gitignoré, créé au runtime)
│   └── src/
│       ├── app/main.py            # create_app() FastAPI + CORS + montage /api
│       ├── api/routes.py          # endpoints REST
│       ├── config/
│       │   ├── settings.py        # pydantic-settings (charge .env)
│       │   └── llm_config.py      # get_llm() → AzureChatOpenAI + load_prompt()
│       ├── db/
│       │   ├── models.py          # schéma SQL + connexion sqlite3
│       │   └── repository.py      # verrou run journalier, historique 14j, persist
│       ├── agents/
│       │   ├── graph.py           # StateGraph LangGraph (assemblage des nodes)
│       │   ├── state.py           # DigestState (TypedDict) + modèles Pydantic
│       │   ├── service.py         # cycle de vie d'un run (verrou → pipeline → statut)
│       │   ├── mcp_tools.py       # accès MCP Exa + Brave (python-sdk mcp)
│       │   ├── search_parse.py    # normalisation d'URL + parsing des résultats MCP
│       │   └── nodes/             # un fichier par étape du pipeline
│       │       ├── load_config.py
│       │       ├── build_queries.py
│       │       ├── search.py
│       │       ├── dedupe.py
│       │       ├── summarize.py
│       │       ├── novelty_check.py
│       │       ├── select.py
│       │       └── persist.py
│       └── assets/
│           ├── tags.txt                  # mots-clés du domaine
│           ├── seed_queries.yaml         # requêtes seed (2 axes thématiques)
│           ├── summary_system_prompt.md  # prompt de résumé
│           └── novelty_prompt.md         # prompt de jugement de nouveauté
│
└── frontend/                      # === Angular v20 (TypeScript) ===
    ├── package.json / angular.json / tsconfig*.json
    ├── proxy.conf.json            # /api → http://localhost:8000 (dev)
    └── src/
        ├── main.ts / index.html / styles.css
        └── app/
            ├── app.config.ts      # providers (HttpClient, zone)
            ├── app.component.ts    # état global : today, historique, polling, sélection
            ├── models/article.model.ts
            ├── services/digest.service.ts    # appels HttpClient vers /api
            └── components/
                ├── digest-list/    # les N cartes + bouton run + statut
                ├── digest-card/    # une carte article
                └── history-sidebar/# 14 derniers jours
```

---

## 3. Backend

### 3.1 Pipeline LangGraph

Graphe **linéaire** compilé dans `agents/graph.py`. L'état partagé `DigestState`
(TypedDict, `agents/state.py`) circule de node en node ; chaque node retourne un
patch partiel de l'état.

| # | Node | Rôle | Entrée → Sortie (clés de l'état) |
|---|------|------|----------------------------------|
| 1 | `load_config` | Charge `tags.txt` et l'historique 14 j (depuis SQLite, **avant** la date du run) | `run_date` → `tags`, `recent_history`, `errors` |
| 2 | `build_queries` | Combine les requêtes seed (2 axes) + une requête fondée sur les tags | `tags` → `queries` |
| 3 | `search` | Lance chaque requête sur Exa **et** Brave, en concurrence (`asyncio.gather`) | `queries` → `raw_candidates`, `errors` |
| 4 | `dedupe` | Normalise les URLs, retire doublons inter-providers et articles déjà vus (14 j) | `raw_candidates`, `recent_history` → `deduped` |
| 5 | `summarize` | Pour chaque candidat : résumé, « pourquoi », tags, cluster, pertinence (LLM, sortie structurée, concurrent) | `deduped` → `summarized` |
| 6 | `novelty_check` | **Un seul** appel LLM classe chaque candidat `NEW` / `DUPLICATE` / `UPDATE` vs l'historique | `summarized`, `recent_history` → `summarized` (annoté) |
| 7 | `select_top` | Écarte les `DUPLICATE`, trie par pertinence puis récence, garde `MAX_ARTICLES_PER_DAY` | `summarized` → `selected` |
| 8 | `persist` | Écrit les articles retenus dans SQLite | `selected` → ∅ |

**Dégradation gracieuse** : chaque source de recherche capture ses erreurs
(timeout, `npx` absent, clé manquante) et retourne une liste vide + un message
dans `errors`, sans interrompre le pipeline. De même, `novelty_check` retombe
sur « tout est NEW » si l'appel LLM échoue.

### 3.2 Cycle de vie d'un run (`agents/service.py`)

```
run_daily_digest(repo, force)
   ├─ try_start_run(today)     # INSERT OR IGNORE dans runs → verrou atomique
   │     └─ False → déjà lancé aujourd'hui → skip
   ├─ run_digest(...)          # exécute le graphe LangGraph
   ├─ finish_run(done)         # ou finish_run(error, message) en cas d'exception
```

L'idempotence « une fois par jour » repose sur la **clé primaire `run_date`** de
la table `runs` : `INSERT OR IGNORE` garantit qu'un seul process démarre le run.

### 3.3 Persistance SQLite (`db/`)

`sqlite3` de la stdlib (aucun service externe, portable, fichier unique).

- **`runs`** : `run_date` (PK, `YYYY-MM-DD` local), `status`
  (`running`/`done`/`error`), horodatages, erreur.
- **`articles`** : url, `normalized_url` (dédup), titre, résumé,
  `why_it_matters`, source, date, `tags_json`, `topic_cluster`, `links_json`,
  `is_update_of` (FK vers l'article complété), `rank`.
- Historique 14 j : `WHERE run_date >= date('now','-14 day')`.
- Une **connexion courte par opération** (pas d'état partagé) → robuste avec les
  `BackgroundTasks` FastAPI.

### 3.4 Recherche via MCP (`agents/mcp_tools.py`, `search_parse.py`)

Les serveurs MCP sont lancés **à la demande** via `npx` (aucune installation
préalable) et pilotés par le **python-sdk `mcp`** (`StdioServerParameters` +
`stdio_client` + `ClientSession`) :

- **Exa** — recherche sémantique : `npx -y mcp-remote https://mcp.exa.ai/mcp?exaApiKey=…`, tool `web_search_exa`.
- **Brave** — recherche web complémentaire : `npx -y @modelcontextprotocol/server-brave-search`, tool `brave_web_search`.

Les réponses MCP sont hétérogènes (JSON ou texte à libellés variables). Le
parseur `search_parse.py` :
- tente d'abord un décodage JSON, sinon parse le format texte
  (`Title:`/`URL:`/`Published:`/`Description:`…) via une **table de
  correspondance** de libellés tolérante ;
- normalise les URLs (retrait `www.`/fragments/paramètres de tracking, tri des
  paramètres) pour produire une **clé de déduplication stable**.

### 3.5 LLM (`config/llm_config.py`)

`AzureChatOpenAI` (LangChain) sur le déploiement **`gpt-5-chat`**. Deux usages :
- **Résumé** : `chain = prompt | llm.with_structured_output(ArticleSummary)` →
  objet Pydantic validé (pas de parsing manuel).
- **Nouveauté** : `llm.with_structured_output(NoveltyReport)` → liste de verdicts.

> Note technique : ce déploiement n'accepte que la température par défaut ;
> `get_llm()` ne transmet donc `temperature` que si elle est explicitement
> fournie.

### 3.6 API REST (`api/routes.py`)

| Méthode | Route | Rôle |
|---|---|---|
| GET  | `/api/health` | readiness (utilisé par `run.py`) |
| GET  | `/api/digest/today` | digest du jour + statut du run |
| GET  | `/api/digest/{YYYY-MM-DD}` | digest d'une date (400 si format invalide) |
| GET  | `/api/history` | index des 14 derniers jours (date, statut, compteur) |
| POST | `/api/run?force=` | déclenche le run en **tâche de fond** (idempotent) |

`POST /run` retourne immédiatement (`running`/`skipped`) ; le frontend **poll**
ensuite `/digest/today` jusqu'à `done`.

---

## 4. Frontend

- **Angular v20**, composants **standalone**, `HttpClient` (`withFetch`), RxJS.
- Le **serveur de dev `ng serve` s'appuie sur esbuild + Vite** — la contrainte
  « projet Vite » est donc satisfaite.
- `proxy.conf.json` route `/api` → `:8000` en dev : le même code (`DigestService`)
  fonctionne en dev et après un `ng build`.
- Répartition :
  - `app.component` — état applicatif : chargement du jour, sélection de date,
    déclenchement du run, **polling** toutes les 4 s pendant un run, historique.
  - `digest-list` — en-tête (date, statut), bouton « Rechercher aujourd'hui »
    (désactivé hors du jour courant ou pendant un run), liste de cartes.
  - `digest-card` — titre cliquable, source · date · cluster, badge « complète un
    sujet précédent » si `is_update_of`, résumé, « pourquoi c'est important »,
    tags, liens.
  - `history-sidebar` — 14 derniers jours cliquables (recharge `digest/{date}`).
- Thème clair/sombre automatique (`prefers-color-scheme`), CSS unique sans
  dépendance externe.

---

## 5. Démarrage & portabilité

`start.sh` / `start.bat` sont **idempotents** et exécutables après un simple
`git clone` :

1. **Garde `.env`** — le crée depuis `.env.example` et s'arrête si absent.
2. **venv Python** — création si absente, `pip install -e backend` derrière un
   fichier sentinelle (réinstalle seulement si `pyproject.toml` change).
3. **`npm install`** — seulement si `node_modules` absent.
4. **Backend** (uvicorn) + **Frontend** (`ng serve`) en arrière-plan.
5. **`run.py`** (stdlib uniquement, portable) attend `/api/health`, déclenche
   `POST /api/run`, ouvre le navigateur.
6. **Arrêt propre** : `trap` (bash) / fenêtres séparées (batch).

Ports surchargeables via `BACKEND_PORT` / `FRONTEND_PORT`.

---

## 6. Choix techniques & justifications

| Choix | Alternative écartée | Pourquoi |
|---|---|---|
| **SQLite (stdlib)** | Postgres/pgvector | Outil local mono-utilisateur : zéro service à installer, un seul fichier, parfaitement portable. |
| **Dédup URL + jugement LLM** | Embeddings vectoriels | Le déploiement Azure disponible n'expose qu'un modèle *chat*, pas d'*embeddings* ; le LLM juge très bien la nouveauté sur un historique compact (~14 j tiennent dans un prompt). Évolution possible vers des vecteurs plus tard. |
| **MCP via `npx`** | SDK/API HTTP dédiés | Aucune dépendance à préinstaller ; réutilise le pattern éprouvé d'`agent-infos`. Contrepartie : réseau + Node requis au 1ᵉʳ appel. |
| **LangGraph linéaire** | Orchestration ad hoc | Étapes explicites, testables une à une, dégradation par node, état typé. |
| **`with_structured_output`** | Parsing de texte libre | Sorties validées par Pydantic, robustes, sans post-traitement fragile. |
| **Angular + Vite (`ng serve`)** | React/Vue | Choix explicite de l'utilisateur ; base Vite conservée via le dev-server Angular. |
| **`run.py` en stdlib pure** | script dans chaque shell | Une seule logique health/run/navigateur, portable mac/linux/windows, appelable hors venv. |
| **Idempotence par clé primaire `run_date`** | fichier lock / drapeau | Atomique, sans course, survit aux redémarrages. |

---

## 7. Configuration

Fichier `backend/.env` (voir `.env.example`) — **gitignoré** :

| Variable | Rôle |
|---|---|
| `AZURE_OPENAI_ENDPOINT` / `_API_KEY` / `_CHAT_DEPLOYMENT` / `_API_VERSION` | LLM Azure OpenAI |
| `EXA_API_KEY` / `BRAVE_API_KEY` | recherche |
| `MAX_ARTICLES_PER_DAY` (5) · `HISTORY_DAYS` (14) · `SEARCH_WINDOW_DAYS` (7) | réglages métier |

Domaine de veille ajustable sans code : `backend/src/assets/tags.txt` et
`seed_queries.yaml`.

---

## 8. Stack & dépendances

**Backend (Python ≥ 3.11)** : `langchain`, `langchain-core`, `langchain-openai`
(`AzureChatOpenAI`), `langgraph`, `mcp` (python-sdk), `fastapi`, `uvicorn`,
`pydantic`, `pydantic-settings`, `httpx`, `PyYAML`, `sqlite3` (stdlib).

**Frontend (Node ≥ 18)** : `@angular/*` v20, `@angular/build` (esbuild/Vite),
`rxjs`, `typescript`, `zone.js`.

**Serveurs MCP (via `npx`, non installés dans le dépôt)** : `mcp-remote` (pont
Exa), `@modelcontextprotocol/server-brave-search`.

---

## 9. Limites connues

- **Réseau + Node requis** : la recherche dépend de `npx` et d'un accès sortant ;
  pas de mode hors-ligne.
- **Fraîcheur des dates** : certaines sources ne renvoient pas de date de
  publication fiable (`N/A`) — géré, mais le tri par récence en pâtit alors.
- **Coût LLM** : ~1 appel de résumé par candidat + 1 appel de nouveauté par run.
  Le nombre de candidats résumés est plafonné (`MAX_ARTICLES_PER_DAY × 3`).
- **Mono-utilisateur** : SQLite local, pas conçu pour un déploiement multi-postes.
