# RoteiroSimples RS 0.15 — layout de blocos e medição

## Implementado

- O novo `-O 5` parte da mesma SSA tipada e alocação de `r13`, `r14`, `r15`/pilha do `-O 4`.
- A função `planejar_layout` constrói traços determinísticos de blocos básicos alcançáveis, iniciando na entrada do CFG.
- Quando a próxima instrução física é o destino de uma aresta incondicional, o `jmp` é eliminado e as cópias `phi` permanecem antes da queda natural.
- Decisões cuja aresta verdadeira ou falsa segue fisicamente podem inverter a condição para reduzir o número de saltos. Arestas com cópias `phi` usam trampolins para manter as cópias no caminho correto.
- Arestas excepcionais de `para`, inclusive o incremento que transborda, seguem preservadas.
- Os níveis anteriores `-O 0..4` permanecem disponíveis e não usam o novo layout.

## Não implementado

- Compressão de saltos relativos para deslocamentos de oito bits, SSA destruída para um IR independente, coalescência avançada ou escalonamento por perfil real.
- Alocador global sofisticado, medição de energia ou garantia de desempenho superior em todos os programas.

## Medição

Execute `python benchmarks/medir.py --repeticoes 7 --json resultados.json` em Linux/Windows x86-64. O benchmark compila `benchmarks/lacos.rts` para `-O 3`, `-O 4`, `-O 5` antes de medir, aquece cada executável uma vez, valida código de retorno e saída e apresenta **mediana de tempo real** por nível. É um microbenchmark, inclui o custo de iniciar um processo e não deve ser generalizado para outros programas.

Para avaliar melhor, repita medições em máquina sem carga, com frequência de CPU estável, ambiente térmico similar e entrada idêntica. Ganho de tamanho não prova aceleração.
