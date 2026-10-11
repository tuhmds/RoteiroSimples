@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === RoteiroSimples - executar programa ja compilado ===
echo.
if not exist "%~dp0roteiro_windows.exe" (
 echo Ainda nao ha executavel. Execute COMPILAR_WINDOWS.bat.
 pause
 exit /b 1
)
"%~dp0roteiro_windows.exe"
set "RS_CODIGO=%errorlevel%"
echo.
echo Fim da execucao. Codigo de saida: %RS_CODIGO%.
echo Aperte uma tecla para fechar esta janela.
echo Para editar ou compilar, abra INICIAR_RS.bat.
pause >nul
exit /b %RS_CODIGO%
