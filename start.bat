@echo off
REM ==========================================================================
REM AI-for-DEV - demarrage tout-en-un (Windows)
REM   - bootstrappe backend Python (venv + deps) et frontend Angular
REM   - demarre uvicorn + ng serve dans des fenetres separees
REM   - declenche la recherche du jour et ouvre le navigateur
REM ==========================================================================
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8000"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=4200"
if "%PYTHON%"=="" set "PYTHON=python"

echo ==^> AI-for-DEV : demarrage

REM --- 1. Garde .env --------------------------------------------------------
if not exist "%BACKEND%\.env" (
  copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
  echo.
  echo   Le fichier backend\.env vient d'etre cree depuis .env.example.
  echo   ^>^>^> Renseignez-y vos cles avant de relancer :
  echo         - AZURE_OPENAI_API_KEY
  echo         - EXA_API_KEY
  echo         - BRAVE_API_KEY
  echo   ^(reprenez ces valeurs depuis ..\agent-infos\.env^)
  echo.
  echo   Fichier a editer : %BACKEND%\.env
  echo.
  exit /b 1
)

REM --- 2. Bootstrap backend -------------------------------------------------
set "VENV=%BACKEND%\.venv"
if not exist "%VENV%" (
  echo ==^> Creation du venv Python
  "%PYTHON%" -m venv "%VENV%"
)
set "VPY=%VENV%\Scripts\python.exe"

if not exist "%VENV%\.deps-installed" (
  echo ==^> Installation des dependances Python
  "%VPY%" -m pip install --upgrade pip -q
  "%VPY%" -m pip install -e "%BACKEND%" -q
  echo done> "%VENV%\.deps-installed"
)

REM --- 3. Bootstrap frontend ------------------------------------------------
if not exist "%FRONTEND%\node_modules" (
  echo ==^> npm install ^(frontend^)
  pushd "%FRONTEND%"
  call npm install
  popd
)

REM --- 4. Demarrage backend (nouvelle fenetre) ------------------------------
echo ==^> Demarrage du backend sur :%BACKEND_PORT%
start "AI-for-DEV backend" cmd /k "cd /d "%BACKEND%" && "%VPY%" -m uvicorn src.app.main:app --host 0.0.0.0 --port %BACKEND_PORT%"

REM --- 5. Demarrage frontend (nouvelle fenetre) -----------------------------
REM CI=1 force le mode non-interactif du Angular CLI (sinon un prompt
REM d'autocompletion/analytics peut bloquer ou faire planter `ng serve`).
echo ==^> Demarrage du frontend sur :%FRONTEND_PORT%
start "AI-for-DEV frontend" cmd /k "cd /d "%FRONTEND%" && set CI=1&& set NG_CLI_ANALYTICS=false&& npm run start -- --port %FRONTEND_PORT%"

REM --- 6. Sante + run du jour + navigateur ----------------------------------
"%PYTHON%" "%ROOT%run.py" --backend-url "http://localhost:%BACKEND_PORT%" --frontend-url "http://localhost:%FRONTEND_PORT%"

echo.
echo ==^> Pret. UI : http://localhost:%FRONTEND_PORT%
echo     (Fermez les fenetres backend/frontend pour tout arreter.)
endlocal
