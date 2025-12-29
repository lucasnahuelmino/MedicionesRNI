@echo off
setlocal
cd /d "%~dp0"

set VENV=.venv
set PORT=8501

echo.
echo ==========================
echo  Ejecutando Streamlit app
echo ==========================
echo.

if not exist "%VENV%\Scripts\activate.bat" (
  echo [ERROR] No existe el venv. Ejecuta primero 00_setup_venv.bat
  pause
  exit /b 1
)

call "%VENV%\Scripts\activate.bat"

if not exist "archivosdata" mkdir archivosdata
if not exist "assets" mkdir assets
if not exist "styles" mkdir styles

REM Abrir navegador (espera un toque a que levante)
start "" http://localhost:%PORT%

REM Ejecutar app
python -m streamlit run app.py --server.port %PORT% --server.headless false

endlocal
