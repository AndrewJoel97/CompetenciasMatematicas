@echo off
setlocal

set "BACKEND_DIR=%~dp0backend_competencias"
set "FRONTEND_DIR=%~dp0competencias-matematicas"
set "BACKEND_PORT=5002"
set "FRONTEND_PORT=4200"

cd /d "%BACKEND_DIR%"
if not exist "venv\Scripts\python.exe" (
  echo Creando virtualenv...
  python -m venv venv
  echo Instalando requirements...
  "venv\Scripts\python.exe" -m pip install --upgrade pip
  "venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
  echo Virtualenv ya existe. Omitiendo instalacion.
)

REM arrancar backend
start "Backend" cmd /k "cd /d %BACKEND_DIR% && call venv\Scripts\activate && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port %BACKEND_PORT%"

timeout /t 2 /nobreak >nul

REM arrancar frontend
start "Frontend" cmd /k "cd /d %FRONTEND_DIR% && npx ng serve --proxy-config proxy.conf.json --port %FRONTEND_PORT%"

endlocal