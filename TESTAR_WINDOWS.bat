@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === RoteiroSimples (RS) 0.1 - Executavel nativo Windows ===
echo.
"%~dp0roteiro_windows.exe"
echo.
echo Pressione qualquer tecla para fechar esta janela.
pause >nul
