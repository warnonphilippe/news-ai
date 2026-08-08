#!/usr/bin/env bash
# ============================================================================
# AI-for-DEV — demarrage tout-en-un (macOS / Linux)
#   - bootstrappe le backend Python (venv + deps) et le frontend Angular
#   - demarre uvicorn + ng serve
#   - declenche la recherche du jour (si pas deja faite)
#   - ouvre le navigateur
# Idempotent : relancable sans risque.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-4200}"
PYTHON="${PYTHON:-python3}"

# --- Choix de la commande d'ouverture de navigateur (informatif) ------------
echo "==> AI-for-DEV : demarrage"

# --- 1. Garde .env ----------------------------------------------------------
if [ ! -f "$BACKEND/.env" ]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
  cat <<EOF

  Le fichier backend/.env vient d'etre cree depuis .env.example.
  >>> Renseignez-y vos cles avant de relancer :
        - AZURE_OPENAI_API_KEY
        - EXA_API_KEY
        - BRAVE_API_KEY
  (Vous pouvez reprendre ces valeurs depuis ../agent-infos/.env)

  Fichier a editer : $BACKEND/.env

EOF
  exit 1
fi

# --- 2. Bootstrap backend (venv + deps) -------------------------------------
VENV="$BACKEND/.venv"
if [ ! -d "$VENV" ]; then
  echo "==> Creation du venv Python"
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

SENTINEL="$VENV/.deps-installed"
if [ ! -f "$SENTINEL" ] || [ "$BACKEND/pyproject.toml" -nt "$SENTINEL" ]; then
  echo "==> Installation des dependances Python"
  python -m pip install --upgrade pip -q
  pip install -e "$BACKEND" -q
  touch "$SENTINEL"
fi

# --- 3. Bootstrap frontend (npm install) ------------------------------------
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "==> npm install (frontend)"
  (cd "$FRONTEND" && npm install)
fi

# --- 4. Demarrage backend ---------------------------------------------------
echo "==> Demarrage du backend sur :$BACKEND_PORT"
(cd "$BACKEND" && python -m uvicorn src.app.main:app --host 0.0.0.0 --port "$BACKEND_PORT") </dev/null &
BACKEND_PID=$!

# --- 5. Demarrage frontend --------------------------------------------------
# CI=1 + stdin sur /dev/null : force le mode NON-INTERACTIF du Angular CLI, sinon
# il tente d'afficher un prompt (autocompletion/analytics) qui, lance en tache de
# fond, est "force closed" et fait planter `ng serve`.
echo "==> Demarrage du frontend sur :$FRONTEND_PORT"
(cd "$FRONTEND" && CI=1 NG_CLI_ANALYTICS=false npm run start -- --port "$FRONTEND_PORT") </dev/null &
FRONTEND_PID=$!

# --- Arret propre -----------------------------------------------------------
cleanup() {
  echo ""
  echo "==> Arret..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- 6. Sante + run du jour + ouverture navigateur --------------------------
"$PYTHON" "$ROOT/run.py" \
  --backend-url "http://localhost:$BACKEND_PORT" \
  --frontend-url "http://localhost:$FRONTEND_PORT" || true

echo ""
echo "==> Pret. UI : http://localhost:$FRONTEND_PORT"
echo "    (Ctrl+C pour tout arreter)"

# Garde le script vivant tant que les serveurs tournent.
wait
