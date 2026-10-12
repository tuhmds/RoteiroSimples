# RS 0.17 — memória e listas verificadas

## Decisões implementadas

`seja nome: lista[N]` declara uma lista de `N` inteiros de 64 bits.
`N` é literal inteiro de 1 a 256, não uma expressão. Elementos em `0..N-1`.
Todos os elementos são zerados na declaração (o código nativo inicializa cada
slot). `lista[índice]` é lido como expressão e `lista[índice] = expr` grava um
inteiro. `leia(lista[índice])` lê um inteiro em um elemento.

Cada elemento ocupa oito bytes. Variáveis escalares e listas compartilham o
mesmo espaço de slots na pilha. O total de slots não pode passar de 256, sem
alocação no heap. O índice é avaliado como inteiro de 64 bits; antes do acesso
há testes para `índice < 0` e `índice >= tamanho`, ambos abortam com código 1
sem efetuar o acesso inválido. O runtime imprime mensagem em português:
`Erro: índice fora dos limites da lista.`. Erros de overflow aritmético em
expressões de índice continuam verificados como nas versões anteriores.

`valor = tamanho(lista)` equivale à constante `N` e não lê a memória.

## Desempenho e integração com SSA

A IR tipada reconhece as instruções de lista. Para evitar otimização insegura
com efeitos/aliasing ainda não representados na SSA, **programas contendo
listas usam o gerador nativo de pilha**, mesmo quando compilados com `-O 4/5/6`.
Operações escalares nesses programas ainda têm o dobramento seguro de
constantes do `-O 1`, mas não usam a propagação local/SSA dos níveis superiores.
Programas sem listas continuam usando os níveis antigos inalterados.

## Contrato para referências futuras (não implementado)

1. Referências seguras deverão carregar a informação de comprimento, origem e
   validade; nenhum acesso descontrolado ao endereço será permitido por padrão.
2. Não será permitida referência pendente após o fim da vida do dado referenciado.
3. Ponteiros brutos exigirão região explicitamente insegura e nunca serão a
   representação implícita de `lista`.
4. Buffers de texto exigirão controle próprio de comprimento e capacidade,
   distinta da quantidade de caracteres Unicode.
5. Antes de suportar escape do escopo ou cópias de listas, definiremos semântica
   de propriedade e empréstimos de memória.

Limitações: listas fixas, unidimensionais e somente de inteiros; sem realocação,
objetos, referências, slices, strings mutáveis ou garbage collector. Protótipo
experimental, não é seguro para produção.
