@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === RoteiroSimples RS 0.23 - compilar e executar ===
echo.
where py >nul 2>nul
if errorlevel 1 (
 echo Python nao foi encontrado. Instale Python 3 e reabra o terminal.
 pause
 exit /b 1
)
py -3 compilar.py exemplos\funcoes_escopos.rts --alvo windows -O 8 -o roteiro_windows.exe
if errorlevel 1 (
 echo.
 echo Nao foi possivel compilar. Confira o erro acima.
 pause
 exit /b 1
)
echo.
echo === Saida do programa ===
"%~dp0roteiro_windows.exe"
set "RS_CODIGO=%errorlevel%"
echo.
echo O programa terminou com o codigo %RS_CODIGO%.
echo Para continuar, abra INICIAR_RS.bat e escolha outra opcao.
pause
exit /b %RS_CODIGO%
