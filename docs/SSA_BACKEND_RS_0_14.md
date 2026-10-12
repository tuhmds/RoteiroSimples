# Backend SSA nativo e alocacao de registradores — RS 0.14

## O que foi implementado

A partir de `-O 4`, a RS passa pela AST e IR tipada, CFG, SSA com nós `phi`,
vivacidade SSA, grafo de interferência, coloração e emissão de código x86-64
**a partir dos blocos SSA**. Cada bloco contém uma instrução elementar da IR
de origem e termina em saltos para seus sucessores; as transferências entre
versões SSA ocorrem **na aresta de entrada do sucessor correto**, e não de
forma especulativa no início de um bloco compartilhado.

As cópias dos `phi` são simultâneas. Para `a <- b; b <- a`, por exemplo,
o backend salva o valor antigo de `a` em um slot temporário, executa
`a <- b` e `b <- temporario`. Os testes executam esse caso em código de
máquina real no Linux e no Windows via CI.

O alocador usa a análise de vivacidade, com usos de `phi` modelados na
**aresta predecessora**. Constrói interferências entre valores simultaneamente
vivos e atribui valores mais utilizados a `r13`, `r14`, `r15` quando não
houver conflito. Outros valores ficam em posições da pilha, que podem ser
reutilizadas caso não haja interferência. Apenas registradores seguros
através das chamadas nativas são utilizados (o runtime de leitura salva
os três). Ainda não existe um alocador global com coalescing e intervalos
refinados, nem spill rewriting em múltiplas etapas.

A instrução de incremento de `para` tem uma saída adicional quando
ocorre overflow. Nesse caminho a versão de saída do contador recebe o
valor **anterior** ao incremento, reproduzindo o comportamento legado.

## Compatibilidade e limites

- `-O 0`, `-O 1`, `-O 2`, `-O 3` permanecem no backend antigo.
- `-O 4` funciona nos executáveis nativos Windows PE32+ e Linux ELF64.
- As novas cópias são emitidas em **todos** os ramos do CFG, inclusive
  ramos `se/senao`, laços e `pare`/`continue`. A construção pode introduzir
  saltos adicionais e executáveis maiores; não reivindicamos aceleração.
- O backend usa três registradores globais e posições de pilha reaproveitadas.
  Há um limite conservador de 256 slots, e o formato PE mantém suas
  seções de 4 KiB. Programas grandes podem falhar na compilação.
- Os níveis de otimização se restringem a números inteiros e lógicos,
  sem ponteiros, referências ou alocação dinâmica.
- Testes de equivalência são necessários para detectar regressões
  semânticas; o compilador continua experimental e não é recomendado
  para sistemas de produção.

## Ferramentas de inspeção

```powershell
py -3 compilar.py exemplos\registradores.rts --alvo windows -O 4 --mostrar-ssa --mostrar-copias-phi --mostrar-alocacao -o roteiro_windows.exe
```

`--mostrar-alocacao` lista, para cada versão SSA, o registrador ou slot
escolhido. Os caminhos O0..O3 continuam disponíveis para comparar saídas
com O4. Próximos ganhos: organizar blocos de modo a remover saltos
incondicionais, comparar tempos de execução, aumentar a capacidade das
seções PE e tornar o alocador progressivamente mais sofisticado.
