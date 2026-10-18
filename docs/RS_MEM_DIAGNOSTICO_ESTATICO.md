# RS-MEM — diagnóstico estático da pressão de memória

Use:

```bash
python -m verificacao.diagnostico_memoria exemplos/listas_dinamicas.rts --json relatorios/memoria.json
```

A ferramenta analisa a AST produzida pelo compilador existente.
Separa ocorrências **sintáticas** de declarações dinâmicas, potenciais
crescimentos, transferências, liberações e reservas. Percorre o corpo
principal, as funções e blocos condicionais e de repetição.

Se um crescimento ocorre dentro de um laço, o relatório sugere estudar
pré-reserva de capacidade. Não aplica nenhuma mudança automaticamente.

**Importante:** o relatório não mede o número real de alocações, tempo,
RSS, fragmentação, custo de operações, comportamento de aliases, escape
de ponteiros, latência, segurança geral ou consumo de RAM. Não confundir
a análise com perfil de execução nem usar os números para alegar ganho.

A ferramenta é portável, não modifica a IR e não interfere no backend,
em O0–O8 ou na saída PE/ELF. Ela prepara os próximos experimentos de
instrumentação nativa, alocação por pools e análise de escape, que exigem
medição e garantias maiores antes de serem implementados automaticamente.
