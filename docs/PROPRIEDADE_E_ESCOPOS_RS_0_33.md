# RS 0.33 — Transferência e gerenciamento de escopos

## O que foi implementado

`mova(destino, origem)` verifica a origem, libera os dados anteriores do
destino, transfere o descritor nativo de três palavras e invalida a origem.
Não há cópia de elementos. `mova` exige duas listas dinâmicas distintas
já declaradas; mover uma lista para si mesma gera erro de compilação.

`lista[]` passa a funcionar em escopos aninhados de `se`, `enquanto` e
`para`. Todos os descritores começam no estado inativo. Ao alcançar uma
declaração, seu descritor se torna uma lista vazia válida. O fechamento do
bloco libera os descritores declarados nele; `pare` e `continue`
liberam também os donos dos blocos abandonados. O retorno de função
libera todos os donos que ainda estejam ativos, inclusive nos caminhos
com retorno antecipado. A propriedade externa aos laços é preservada.

## Segurança e limitações

Uma origem após movimento não permite acesso, inclusão ou liberação,
exceto como destino de outra transferência. Os elementos são inteiros
de 64 bits, e não há empréstimos, referências públicas, transferência
para parâmetros e retornos, listas genéricas ou estruturas compostas
de propriedade. O tipo de origem é verificado estaticamente, mas seu
estado após movimentação é conferido em execução.

Falhas fatais não fazem o desenrolamento das estruturas antes de encerrar
o processo. As páginas são recuperadas pelo sistema operacional.
Este recurso ainda não foi auditado para produção. Consulte os testes
e o exemplo `exemplos/propriedade_escopos.rts`.
