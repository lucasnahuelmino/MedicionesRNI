@echo off
setlocal
cd /d "%~dp0"

set VENV=.venv

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

REM Asegura carpetas esperadas
if not exist "archivosdata" mkdir archivosdata
if not exist "assets" mkdir assets
if not exist "styles" mkdir styles

REM Ejecutar (robusto)
python -m streamlit run app.py --server.port 8501 --server.headless false

endlocal

