@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === RoteiroSimples 0.2 - Biblioteca matematica ===
echo.
py -3 compilar.py exemplos\matematica.rts --alvo windows -o roteiro_windows.exe
if errorlevel 1 (
 echo Erro ao compilar. Verifique se Python 3 esta instalado.
 pause
 exit /b 1
)
echo.
echo === Resultado ===
roteiro_windows.exe
echo.
pause
