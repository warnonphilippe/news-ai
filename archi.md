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
│       │   ├── scoring.py         # dates, décote de fraîcheur, poids de source, score final
│       │   └── nodes/             # un fichier par étape du pipeline
│       │       ├── load_config.py
│       │       ├── build_queries.py
│       │       ├── search.py
│       │       ├── dedupe.py
│       │       ├── filter_recent.py
│       │       ├── summarize.py
│       │       ├── novelty_check.py
│       │       ├── select.py
│       │       └── persist.py
│       └── assets/
│           ├── tags.txt                  # mots-clés du domaine
│           ├── seed_queries.yaml         # requêtes seed (2 axes thématiques)
│           ├── source_weights.yaml       # pondération des domaines (autorité)
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
| 3 | `search` | Lance chaque requête sur Exa **et** Brave, en concurrence (`asyncio.gather`) ; Exa reçoit `startPublishedDate` (filtrage de fraîcheur à la source) | `queries` → `raw_candidates`, `errors` |
| 4 | `dedupe` | Normalise les URLs, retire doublons inter-providers et articles déjà vus (14 j) | `raw_candidates`, `recent_history` → `deduped` |
| 5 | `filter_recent` | Applique la fenêtre de fraîcheur (Brave ne filtre pas à la source) et **ordonne du plus frais au plus ancien** | `deduped` → `deduped` (filtré, trié, `age_days`) |
| 6 | `summarize` | Pour chaque candidat : résumé, « pourquoi », tags, cluster, pertinence (LLM, sortie structurée, concurrent) | `deduped` → `summarized` |
| 7 | `novelty_check` | **Un seul** appel LLM classe chaque candidat `NEW` / `DUPLICATE` / `UPDATE` vs l'historique | `summarized`, `recent_history` → `summarized` (annoté) |
| 8 | `select_top` | Écarte les `DUPLICATE`, calcule le **score pondéré** et garde `MAX_ARTICLES_PER_DAY` | `summarized` → `selected` |
| 9 | `persist` | Écrit les articles retenus **et les composantes du score** dans SQLite | `selected` → ∅ |

**Dégradation gracieuse** : chaque source de recherche capture ses erreurs
(timeout, `npx` absent, clé manquante) et retourne une liste vide + un message
dans `errors`, sans interrompre le pipeline. De même, `novelty_check` retombe
sur « tout est NEW » si l'appel LLM échoue.

### 3.2 Critères de sélection (`agents/scoring.py`)

Le classement final **n'utilise pas la pertinence brute du LLM seule** : celle-ci
est pondérée par deux facteurs objectifs.

```
score_final = relevance (LLM, 0-100)
            × facteur_fraîcheur        (décote d'ancienneté)
            × facteur_source           (autorité du domaine)
```

| Composante | Origine | Détail |
|---|---|---|
| `relevance` | LLM (`ArticleSummary.relevance`) | 0–100, jugé sur titre + extrait, pour l'audience « IA for DEV » Java/Python |
| `facteur_fraîcheur` | calculé | 1.0 à ≤ 1 j → décroissance linéaire jusqu'à 0.6 en fin de fenêtre → plancher 0.25 au-delà. Article sans date exploitable : `UNDATED_FRESHNESS_FACTOR` (0.75) |
| `facteur_source` | `assets/source_weights.yaml` | match par **suffixe** de domaine (`blog.jetbrains.com` hérite de `jetbrains.com`). > 1 pour les sources primaires (éditeurs, docs officielles), < 1 pour les agrégateurs / contenus SEO |

**Fenêtre de fraîcheur** (`SEARCH_WINDOW_DAYS`, 7 j par défaut) : appliquée deux
fois — à la source via `startPublishedDate` (Exa) et uniformément par le node
`filter_recent` (nécessaire car Brave ne la supporte pas). Un **repli** évite un
digest vide : si trop peu d'articles entrent dans la fenêtre, les moins anciens
complètent la liste (ils restent pénalisés au scoring).

**Auditabilité** : les quatre composantes (`relevance`, `age_days`,
`freshness_factor`, `source_factor`) sont persistées avec `final_score`, exposées
par l'API et affichées dans l'UI (badge « score », détail au survol).

**Parsing des dates** : les sources renvoient des formats hétérogènes — ISO 8601
(`2026-08-13T00:00:00.000Z`), `YYYY-MM-DD`, relatif (`3 days ago`), ou `N/A`.
`scoring.parse_published()` les normalise ; une date illisible donne `None`
(article conservé mais pénalisé), jamais une erreur.

### 3.3 Cycle de vie d'un run (`agents/service.py`)

```
run_daily_digest(repo, force)
   ├─ try_start_run(today)     # INSERT OR IGNORE dans runs → verrou atomique
   │     └─ False → déjà lancé aujourd'hui → skip
   ├─ run_digest(...)          # exécute le graphe LangGraph
   ├─ finish_run(done)         # ou finish_run(error, message) en cas d'exception
```

L'idempotence « une fois par jour » repose sur la **clé primaire `run_date`** de
la table `runs` : `INSERT OR IGNORE` garantit qu'un seul process démarre le run.

### 3.4 Persistance SQLite (`db/`)

`sqlite3` de la stdlib (aucun service externe, portable, fichier unique).

- **`runs`** : `run_date` (PK, `YYYY-MM-DD` local), `status`
  (`running`/`done`/`error`), horodatages, erreur.
- **`articles`** : url, `normalized_url` (dédup), titre, résumé,
  `why_it_matters`, source, date, `tags_json`, `topic_cluster`, `links_json`,
  `is_update_of` (FK vers l'article complété), `rank`, et les composantes du
  score : `relevance`, `age_days`, `freshness_factor`, `source_factor`,
  `final_score`.
- Historique 14 j : `WHERE run_date >= date('now','-14 day')`.
- Une **connexion courte par opération** (pas d'état partagé) → robuste avec les
  `BackgroundTasks` FastAPI.
- **Migrations** : `models._migrate()` ajoute en `ALTER TABLE` les colonnes
  introduites après coup (idempotent), ce qui préserve l'historique des bases
  existantes.

### 3.5 Recherche via MCP (`agents/mcp_tools.py`, `search_parse.py`)

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

### 3.6 LLM (`config/llm_config.py`)

`AzureChatOpenAI` (LangChain) sur le déploiement **`gpt-5-chat`**. Deux usages :
- **Résumé** : `chain = prompt | llm.with_structured_output(ArticleSummary)` →
  objet Pydantic validé (pas de parsing manuel).
- **Nouveauté** : `llm.with_structured_output(NoveltyReport)` → liste de verdicts.

> Note technique : ce déploiement n'accepte que la température par défaut ;
> `get_llm()` ne transmet donc `temperature` que si elle est explicitement
> fournie.

### 3.7 API REST (`api/routes.py`)

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
| **Score = relevance × fraîcheur × source** | pertinence LLM brute | La pertinence seule laissait remonter des articles vieux de plusieurs mois. La pondération multiplicative garde une échelle lisible et des composantes auditables séparément. |
| **Pondération de source en YAML** | liste en dur / ML | Ajustable par le développeur sans toucher au code, et assumée comme un choix éditorial explicite plutôt que caché. |
| **Fenêtre appliquée 2 fois** (Exa + `filter_recent`) | uniquement à la source | Brave ne supporte pas `startPublishedDate` : sans le node, la moitié du vivier échapperait au filtre. |
| **Repli si trop peu d'articles frais** | fenêtre stricte | Évite un digest vide un jour creux ; les articles de repli restent pénalisés au score. |

---

## 7. Configuration

Fichier `backend/.env` (voir `.env.example`) — **gitignoré** :

| Variable | Rôle |
|---|---|
| `AZURE_OPENAI_ENDPOINT` / `_API_KEY` / `_CHAT_DEPLOYMENT` / `_API_VERSION` | LLM Azure OpenAI |
| `EXA_API_KEY` / `BRAVE_API_KEY` | recherche |
| `MAX_ARTICLES_PER_DAY` (5) · `HISTORY_DAYS` (14) · `SEARCH_WINDOW_DAYS` (7) | réglages métier |
| `UNDATED_FRESHNESS_FACTOR` (0.75) | pénalité des articles sans date exploitable |

Ajustable sans code, dans `backend/src/assets/` : `tags.txt` (mots-clés),
`seed_queries.yaml` (requêtes, 2 axes) et `source_weights.yaml` (autorité des
domaines).

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

### Sur la qualité de la sélection

- **Pertinence non calibrée entre articles.** Chaque candidat est noté dans un
  appel LLM **isolé** : le modèle ne voit jamais les autres candidats. En
  pratique les notes se tassent (mesuré : 82–95, écart-type 4.3), si bien que la
  pertinence discrimine *moins* que les facteurs de fraîcheur et de source.
  Un scoring **comparatif** (un seul appel classant tous les candidats) est la
  correction naturelle.
- **Aucun signal de qualité objectif.** Vérifié : ni Exa (via MCP) ni Brave ne
  renvoient de score — Exa expose `Title/URL/Published/Author/Highlights/Text`,
  Brave `Title/Description/URL`. Aucune évaluation communautaire (points Hacker
  News, étoiles GitHub, citations) n'est consultée.
- **`source_weights.yaml` est un a priori éditorial**, pas une mesure : il juge
  l'éditeur, pas l'article. Un billet faible sur un domaine bonifié reste bonifié.
- **Jugement sur extrait** : le LLM ne lit jamais l'article complet, seulement le
  titre et un extrait tronqué à 4000 caractères.
- **Troncature avant scoring** : seuls les `MAX_ARTICLES_PER_DAY × 3` premiers
  candidats sont résumés. `filter_recent` ordonne désormais le vivier par
  fraîcheur, mais un bon article très en aval reste hors du champ.

### Techniques

- **Réseau + Node requis** : la recherche dépend de `npx` et d'un accès sortant ;
  pas de mode hors-ligne.
- **Dates hétérogènes** : `scoring.parse_published()` couvre ISO 8601,
  `YYYY-MM-DD` et les formats relatifs ; toute date illisible donne `None`
  (article conservé mais pénalisé par `UNDATED_FRESHNESS_FACTOR`).
- **Coût LLM** : ~1 appel de résumé par candidat + 1 appel de nouveauté par run.
- **Ressources complémentaires non implémentées** : `links_json` est toujours
  vide (le modèle `ArticleSummary` n'a pas de champ `links`).
- **Mono-utilisateur** : SQLite local, pas conçu pour un déploiement multi-postes.
