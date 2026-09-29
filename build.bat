@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Territory_Mapping_API - generador del .exe
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

echo [1/4] Preparando entorno virtual...
if not exist ".venv\Scripts\python.exe" (
    %PYEXE% -m venv .venv
    if errorlevel 1 (
        echo ERROR: no se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

echo [2/4] Instalando dependencias...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: fallo la instalacion de dependencias.
    echo        Revisa tu conexion a internet.
    pause
    exit /b 1
)

echo [3/4] Compilando el ejecutable...
pyinstaller --noconfirm --onefile --console ^
    --name Territory_Mapping_API ^
    --paths "%~dp0src" ^
    --collect-submodules uvicorn ^
    --distpath "%~dp0dist" ^
    --workpath "%~dp0build" ^
    --specpath "%~dp0build" ^
    "src\api.py"
if errorlevel 1 (
    echo ERROR: fallo la compilacion.
    pause
    exit /b 1
)

echo [4/4] Probando el ejecutable...
"dist\Territory_Mapping_API.exe" --version
if errorlevel 1 (
    echo ADVERTENCIA: el ejecutable se genero pero no respondio a --version.
)

echo.
echo ==========================================
echo   Listo.
echo   Ejecutable: %~dp0dist\Territory_Mapping_API.exe
echo ==========================================
echo.
echo Para levantar la API:
echo   dist\Territory_Mapping_API.exe
echo.
pause
