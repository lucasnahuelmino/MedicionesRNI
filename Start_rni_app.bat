@echo off
REM Script para iniciar la aplicación Streamlit usando el Python del entorno virtual local (.venv)
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m streamlit run app.py
) else (
  python -m streamlit run app.py
)
exit /b
