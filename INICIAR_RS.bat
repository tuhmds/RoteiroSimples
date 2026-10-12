@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
:MENU
cls
echo ==============================================
echo         RoteiroSimples RS 0.23
echo ==============================================
echo.
echo  [1] Compilar e executar funcoes e escopos (RS 0.23)
echo  [2] Editar o exemplo no Bloco de Notas
echo  [3] Rodar testes automatizados
 echo  [4] Executar o ultimo .exe gerado
 echo  [5] Mostrar arvore sintatica e grafo de fluxo
 echo  [6] Mostrar fluxo de dados e salvar analise.json
 echo  [7] Mostrar atribuicao unica e gerar ssa.json
 echo  [8] Mostrar copias dos nos de juncao
 echo  [9] Ver alocacao de registradores e pilha
 echo  [A] Medicao de desempenho -O 3, -O 4, -O 5 e -O 6
echo  [B] Mostrar efeitos de memoria e E/S
echo  [C] Mostrar memoria versionada e salvar memoria.json
echo  [D] Mostrar propagacao de memoria entre blocos (-O 8)
echo  [0] Sair
 echo.
choice /c 1234567890ABCD /n /m "Escolha uma opcao: "
if errorlevel 14 goto OTIMIZACAO_MEMORIA
if errorlevel 13 goto MEMORY_SSA
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
notepad "%~dp0exemplos\funcoes_escopos.rts"
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
:OTIMIZACAO_MEMORIA
py -3 compilar.py exemplos\memoria_entre_blocos.rts --alvo windows -O 8 --mostrar-ir -o roteiro_windows.exe
if errorlevel 1 echo Falha ao mostrar IR otimizada.
pause
goto MENU
:MEMORY_SSA
py -3 compilar.py exemplos\memory_ssa.rts --alvo windows -O 6 --mostrar-memoria-versionada --salvar-memoria-versionada memoria.json -o roteiro_windows.exe
if errorlevel 1 echo Falha ao analisar a memoria versionada.
echo.
pause
goto MENU
:FIM
endlocal
exit /b
