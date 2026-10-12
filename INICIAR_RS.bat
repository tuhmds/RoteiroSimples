@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
:MENU
cls
echo ==============================================
echo         RoteiroSimples RS 0.8
echo ==============================================
echo.
echo  [1] Compilar e executar exemplo de otimizacao e verificacao
echo  [2] Editar o exemplo no Bloco de Notas
echo  [3] Rodar testes automatizados
 echo  [4] Executar o ultimo .exe gerado
 echo  [0] Sair
 echo.
choice /c 12340 /n /m "Escolha uma opcao: "
if errorlevel 5 goto FIM
if errorlevel 4 goto EXECUTAR
if errorlevel 3 goto TESTES
if errorlevel 2 goto EDITAR
if errorlevel 1 goto COMPILAR
:COMPILAR
call "%~dp0COMPILAR_WINDOWS.bat"
goto MENU
:EDITAR
notepad "%~dp0exemplos\otimizacao.rts"
goto MENU
:TESTES
py -3 -m unittest discover -s testes -v
if errorlevel 1 echo Testes nao aprovados: confira as mensagens acima.
pause
goto MENU
:EXECUTAR
if not exist "%~dp0roteiro_windows.exe" (
 echo Ainda nao ha executavel. Escolha a opcao 1 primeiro.
) else (
 "%~dp0roteiro_windows.exe"
 echo.
 echo Codigo de saida: %errorlevel%
)
pause
goto MENU
:FIM
endlocal
exit /b
