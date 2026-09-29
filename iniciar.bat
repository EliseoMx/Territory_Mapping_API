@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Territory_Mapping_API - servidor
echo ==========================================
echo.

set "PYEXE=py -3"
py -3 --version >nul 2>&1
if errorlevel 1 (
    set "PYEXE=python"
    python --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: no se encontro Python en este equipo.
        echo        Descargalo de https://www.python.org/downloads/
        echo        y al instalar marca "Add python.exe to PATH".
        echo.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Preparando entorno virtual...
    %PYEXE% -m venv .venv
    if errorlevel 1 (
        echo ERROR: no se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
python -c "import fastapi, uvicorn, PIL" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias...
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo ERROR: fallo la instalacion de dependencias.
        echo        Revisa tu conexion a internet.
        pause
        exit /b 1
    )
)

echo.
python "src\api.py" %*
pause
