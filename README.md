# IA for DEV — Digest quotidien d'articles IA

Application **locale** de veille technologique pour développeurs et architectes
**Java / Python**. Chaque jour, en un clic, elle recherche les articles les plus
pertinents sur l'« IA for DEV », les résume, écarte les redites et présente une
sélection courte à lire en **15 à 30 minutes**.

> Détails d'implémentation, structure et choix techniques : voir
> [archi.md](archi.md).

---

## Fonctionnalités

- **Recherche quotidienne ciblée** sur deux axes :
  1. les **outils de dev assistés par IA** (Claude, GitHub Copilot, Cursor, MCP…),
  2. l'**intégration de l'IA dans les applications** (LLM, RAG, agents,
     LangChain/LangGraph, Spring AI…).
- **Sources multiples** : recherche sémantique **Exa** + recherche web
  complémentaire **Brave**, via des serveurs MCP spécialisés.
- **Résumés générés par IA** : pour chaque article, un résumé factuel, une phrase
  « **pourquoi c'est important** pour un dev Java/Python », des tags et un thème.
- **Sélection resserrée** : **5 articles par jour** (configurable), classés par
  un score combinant **pertinence × fraîcheur × autorité de la source**.
- **Articles récents uniquement** : seuls les articles publiés dans les 7 derniers
  jours (configurable) sont retenus, avec un repli les jours creux.
- **Score transparent** : chaque carte affiche son score ; le détail du calcul
  (pertinence, fraîcheur, source) s'affiche au survol.
- **Anti-redites sur 14 jours** : un article déjà présenté n'est pas remontré…
  - …**sauf** s'il **complète** de façon importante un sujet passé — il est alors
    affiché avec un badge « complète un sujet précédent ».
- **Historique** : navigation dans les 14 derniers jours depuis une barre latérale.
- **Un seul run par jour** : relancer l'application le même jour réaffiche
  instantanément la sélection sans relancer de recherche.
- **UI web sobre** : cartes lisibles, liens vers les sources, thème clair/sombre
  automatique.
- **Lancement en une commande**, portable après un simple `git clone`
  (macOS/Linux **et** Windows).

---

## Prérequis

- **Python ≥ 3.11** (`python3`)
- **Node.js ≥ 18** + **npm** (fournit `npx`, utilisé pour les serveurs de recherche)
- Un **accès réseau sortant**
- Des **clés** : Azure OpenAI (LLM), Exa et Brave (recherche)

---

## Lancement

```bash
git clone <repo>
cd news
./start.sh            # macOS / Linux
```

Sous **Windows** :

```bat
start.bat
```

### Première fois : renseigner les clés

Au premier lancement, le script crée `backend/.env` depuis `backend/.env.example`
puis s'arrête en vous demandant de renseigner :

```dotenv
AZURE_OPENAI_API_KEY=...
EXA_API_KEY=...
BRAVE_API_KEY=...
```

> Ces valeurs peuvent être reprises telles quelles depuis le projet voisin
> `../agent-infos/.env`.

Relancez ensuite le script. Il s'occupe de **tout** (idempotent, relançable sans
risque) :

1. crée l'environnement Python et installe les dépendances du backend ;
2. installe les dépendances du frontend (`npm install`) ;
3. démarre le backend (port **8000**) et le frontend (port **4200**) ;
4. lance la **recherche du jour** si elle n'a pas déjà eu lieu ;
5. ouvre `http://localhost:4200` dans le navigateur.

`Ctrl+C` arrête proprement l'ensemble (sous Windows, fermez les deux fenêtres
ouvertes).

### Ports personnalisés

```bash
BACKEND_PORT=8100 FRONTEND_PORT=4300 ./start.sh
```

---

## Utilisation

- L'écran principal affiche la **sélection du jour**. Chaque carte : titre
  cliquable (source), résumé, « pourquoi c'est important », tags, et éventuels
  liens complémentaires.
- Le bouton **« Rechercher aujourd'hui »** relance la recherche du jour (utile si
  le run automatique a échoué) ; une recherche prend en général **1 à 3 minutes**.
- La **barre latérale « Historique »** liste les 14 derniers jours ; cliquez une
  date pour revoir sa sélection.

---

## Configuration

Réglages dans `backend/.env` :

| Variable | Défaut | Rôle |
|---|---|---|
| `MAX_ARTICLES_PER_DAY` | `5` | nombre d'articles présentés par jour |
| `HISTORY_DAYS` | `14` | profondeur de l'historique / anti-redites |
| `SEARCH_WINDOW_DAYS` | `7` | âge maximum d'un article retenu (jours) |
| `UNDATED_FRESHNESS_FACTOR` | `0.75` | pénalité des articles sans date exploitable |

Le **domaine de veille** s'ajuste sans toucher au code :
- `backend/src/assets/tags.txt` — mots-clés suivis ;
- `backend/src/assets/seed_queries.yaml` — requêtes de recherche (2 axes) ;
- `backend/src/assets/source_weights.yaml` — pondération des sources : `> 1.0`
  pour prioriser un domaine (éditeurs, docs officielles), `< 1.0` pour
  rétrograder (agrégateurs). Le match se fait par suffixe de domaine.

### Comment les 5 articles sont choisis

```
score final = pertinence (0-100, jugée par le LLM)
            × facteur de fraîcheur (1.0 récent → 0.25 ancien)
            × facteur de source    (source_weights.yaml)
```

Les articles hors fenêtre sont écartés en amont, puis les doublons des 14
derniers jours, et enfin les 5 meilleurs scores sont retenus. Les composantes du
score sont conservées en base et consultables dans l'UI.

> Limite à connaître : la pertinence est un jugement du LLM sur un extrait, sans
> évaluation externe (ni score fournisseur, ni signal communautaire). Voir
> [archi.md § 9](archi.md) pour le détail des limites.

---

## Dépannage

- **« Backend indisponible »** au démarrage : le premier lancement installe les
  dépendances et peut être lent ; relancez `./start.sh`.
- **Aucun article / erreurs de recherche** : vérifiez l'accès réseau et les clés
  `EXA_API_KEY` / `BRAVE_API_KEY` dans `backend/.env` (les serveurs de recherche
  sont téléchargés via `npx` au premier appel).
- **Port déjà utilisé** : relancez avec `BACKEND_PORT` / `FRONTEND_PORT`.
- **Forcer une nouvelle recherche le même jour** :
  `curl -X POST "http://localhost:8000/api/run?force=true"`.

---

## Notes

- `backend/.env` (secrets) et `backend/data/news.db` (base locale) ne sont pas
  versionnés.
- Angular v20 utilise esbuild/Vite pour son serveur de développement : le
  frontend repose bien sur une base Vite.
