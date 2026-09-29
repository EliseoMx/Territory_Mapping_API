@echo off
setlocal
cd /d "%~dp0"

set "URL=http://127.0.0.1:8000"

curl.exe -s -f "%URL%/salud" >nul 2>&1
if errorlevel 1 (
    echo La API no responde en %URL%
    echo Abre primero iniciar.bat y deja esa ventana abierta.
    pause
    exit /b 1
)

if not exist "salida" mkdir "salida"

echo Generando el mapa del territorio de ejemplo...
curl.exe -s -f -X POST "%URL%/imagen" ^
    -H "Content-Type: application/json" ^
    --data-binary "@samples\territorio_ejemplo.json" ^
    -D "salida\encabezados.txt" ^
    -o "salida\territorio_ejemplo_area.png"
if errorlevel 1 (
    echo ERROR: la API respondio con error.
    pause
    exit /b 1
)

echo.
findstr /i "x-area x-perimetro x-orden" "salida\encabezados.txt"
echo.
echo Abriendo la imagen...
start "" "salida\territorio_ejemplo_area.png"
