@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
:MENU
cls
echo ==============================================
echo         RoteiroSimples RS 0.19
echo ==============================================
echo.
echo  [1] Compilar e executar exemplo de entrada bufferizada (-O 6)
echo  [2] Editar o exemplo no Bloco de Notas
echo  [3] Rodar testes automatizados
 echo  [4] Executar o ultimo .exe gerado
 echo  [5] Mostrar AST e CFG e gerar fluxo.dot
 echo  [6] Mostrar fluxo de dados e salvar analise.json
 echo  [7] Mostrar SSA e gerar ssa.json
 echo  [8] Mostrar plano de copias phi por aresta
 echo  [9] Ver alocacao de registradores e pilha
 echo  [A] Benchmark de velocidade -O 3, -O 4, -O 5 e -O 6
echo  [B] Mostrar efeitos de memoria e E/S
echo  [0] Sair
 echo.
choice /c 1234567890AB /n /m "Escolha uma opcao: "
if errorlevel 12 goto EFEITOS
if errorlevel 11 goto BENCHMARK
if errorlevel 10 goto FIM
if errorlevel 9 goto ALOCACAO
if errorlevel 8 goto COPIAS
if errorlevel 7 goto SSA
if errorlevel 6 goto DADOS
if errorlevel 5 goto GRAFO
if errorlevel 4 goto EXECUTAR
if errorlevel 3 goto TESTES
if errorlevel 2 goto EDITAR
if errorlevel 1 goto COMPILAR
:COMPILAR
call "%~dp0COMPILAR_WINDOWS.bat"
goto MENU
:EDITAR
notepad "%~dp0exemplos\entrada_bufferizada.rts"
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
:GRAFO
py -3 compilar.py exemplos\coalescencia.rts --alvo windows --mostrar-ast --mostrar-cfg --salvar-cfg fluxo.dot -o roteiro_windows.exe
if errorlevel 1 echo Falha ao gerar a AST e o CFG.
echo.
echo O diagrama foi salvo em fluxo.dot.
pause
goto MENU
:DADOS
py -3 compilar.py exemplos\coalescencia.rts --alvo windows -O 2 --mostrar-fluxo --salvar-fluxo analise.json -o roteiro_windows.exe
if errorlevel 1 echo Falha na analise de fluxo.
pause
goto MENU
:SSA
py -3 compilar.py exemplos\ssa.rts --alvo windows -O 2 --mostrar-ssa --salvar-ssa ssa.json -o roteiro_windows.exe
if errorlevel 1 echo Falha ao gerar a SSA.
echo.
pause
goto MENU
:COPIAS
py -3 compilar.py exemplos\coalescencia.rts --alvo windows -O 6 --mostrar-copias-phi -o roteiro_windows.exe
if errorlevel 1 echo Falha ao mostrar copias de phi.
pause
goto MENU
:ALOCACAO
py -3 compilar.py exemplos\coalescencia.rts --alvo windows -O 6 --mostrar-alocacao -o roteiro_windows.exe
if errorlevel 1 echo Falha na alocacao de registradores.
pause
goto MENU
:BENCHMARK
py -3 benchmarks\medir.py --repeticoes 7 --json resultados.json
if errorlevel 1 echo Nao foi possivel concluir o benchmark.
pause
goto MENU
:EFEITOS
py -3 compilar.py exemplos\entrada_bufferizada.rts --alvo windows -O 6 --mostrar-efeitos --salvar-efeitos efeitos.json -o roteiro_windows.exe
if errorlevel 1 echo Falha ao mostrar efeitos da IR.
pause
goto MENU
:FIM
endlocal
exit /b
