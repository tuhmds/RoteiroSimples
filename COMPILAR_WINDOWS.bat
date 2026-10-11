@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === RoteiroSimples (RS) 0.1 - Compilar exemplo ===
echo.
py -3 compilar.py exemplos\ola.rts --alvo windows -o roteiro_windows.exe
if errorlevel 1 (
    echo.
    echo Nao foi possivel compilar. Confira se Python 3 esta instalado.
    pause
    exit /b 1
)
echo.
echo === Resultado ===
"%~dp0roteiro_windows.exe"
echo.
pause
