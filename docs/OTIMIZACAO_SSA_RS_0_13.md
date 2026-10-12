# RoteiroSimples RS 0.13 — SSA utilizada pelo otimizador

## Fluxo implementado

```text
AST -> IR tipada -> dobramento (-O1) -> propagação local (-O2)
    -> CFG e SSA pruned (-O3) -> propagação conservadora entre blocos
    -> reescrita de expressões inteiramente constantes -> vivacidade e
    remoção de atribuições constantes mortas -> backend x86-64 existente
    -> PE32+ Windows ou ELF64 Linux
```

### Garantias e limitações

A SSA validada associa cada leitura à versão correspondente a uma definição,
com `phi` em junções; o otimizador só trata um `phi` como constante quando
**todos os predecessores** apontam para o mesmo valor conhecido. Se um valor é
lido da entrada, os caminhos discordam ou há ciclo ainda não resolvido, a
informação é tratada como desconhecida. Não inferimos que um ramo é
inatingível apenas porque a condição aparenta ser constante.

Há dois estados abstratos além dos inteiros: indefinido e variável. A análise
usa um ponto fixo monotônico; a transformação exige valor conhecido e seguro.
Overflow de 64 bits, divisor zero e `INT64_MIN / -1` não são simplificados.
Nenhuma instrução de entrada/saída é removida ou movida. Depois da propagação,
a análise de vivacidade identifica atribuições com RHS **literal** e destino
sem uso posterior. Somente essas atribuições são eliminadas.

O programa otimizado ainda usa as variáveis originais como slots de pilha:
**não há alocação de registradores nem baixamento SSA nativo**. O arquivo
`compilador/ssa_baixamento.py` planeja as cópias de cada aresta `phi` como
operações **paralelas**, mas não as insere no binário. Para fazer o baixamento
de verdade, precisamos resolver ciclos (movimentos simultâneos), dividir
arestas críticas, manter a semântica de `pare`/`continue` e adaptar o backend.

### Comparação reproduzível

```bash
python3 compilar.py exemplos/ssa_otimizacao.rts --alvo linux -O 2 -o rs_o2
python3 compilar.py exemplos/ssa_otimizacao.rts --alvo linux -O 3 -o rs_o3
wc -c rs_o2 rs_o3
./rs_o2
./rs_o3
python3 -m unittest discover -s testes -v
```

No Windows, a seção PE é alinhada por blocos e o **tamanho do executável pode
ser idêntico** apesar de haver menos instruções internas. Ganhos de velocidade
não são afirmados sem benchmarks repetíveis.

**Próxima etapa:** emissão real das cópias `phi` para um backend baseado em CFG,
seguida de atribuição de registradores e alocação de spill sob regras ABI.
