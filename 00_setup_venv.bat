@echo off
setlocal
cd /d "%~dp0"

REM -----------------------------
REM Config
REM -----------------------------
set VENV=.venv

echo.
echo ==========================================
echo  Setup VENV + dependencias (RNI ENACOM)
echo ==========================================
echo.

REM Chequeo Python
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] No se encontro "python" en PATH.
  echo Instala Python 3.10+ y marca "Add Python to PATH".
  pause
  exit /b 1
)

REM Crear venv si no existe
if not exist "%VENV%" (
  echo [INFO] Creando entorno virtual: %VENV%
  python -m venv "%VENV%"
) else (
  echo [INFO] Ya existe el entorno virtual: %VENV%
)

REM Activar venv
call "%VENV%\Scripts\activate.bat"

REM Actualizar pip
echo [INFO] Actualizando pip...
python -m pip install --upgrade pip

REM Instalar requirements
if exist requirements.txt (
  echo [INFO] Instalando dependencias desde requirements.txt...
  python -m pip install -r requirements.txt
) else (
  echo [WARN] No existe requirements.txt. Instalando dependencias base...
  python -m pip install streamlit pandas numpy Pillow openpyxl pydeck plotly python-docx reportlab kaleido
)

echo.
echo [OK] Entorno listo. Para correr la app usa: 01_run_app.bat
echo.
pause
endlocal
