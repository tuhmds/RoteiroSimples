# RS 0.33 — Listas dinâmicas tipadas

## Sintaxe

- `lista[]` permanece compatível e equivale a `lista[inteiro]`.
- `lista[logico]` aceita `verdadeiro`, `falso` e expressões lógicas.
- `lista[Nome]` aceita o registro previamente declarado com `tipo Nome`.
- `emprestimo[lista]` equivale a `emprestimo[lista[inteiro]]`.
- `emprestimo[lista[logico]]` e `emprestimo[lista[Nome]]` permitem
  leitura temporária em funções, sem transferência de propriedade.

## Propriedade e armazenamento

Listas do mesmo tipo podem trocar a propriedade com `mova(destino, origem)`;
a origem fica inativa. As listas possuem quantidade e capacidade em elementos,
e o crescimento duplica a capacidade sempre que necessário. Registros com
vários campos consomem diversas palavras de 64 bits por elemento; a alocação,
cópia e desalocação calculam o tamanho usando o tipo definido.

`adicione(dados, registro)` acrescenta uma **cópia completa** dos campos do
registro. A expressão `seja copia: Nome = dados[indice]` copia o elemento
de volta para o quadro local. A cópia continua independente da lista e
também do registro original. O código valida índices antes de acessar memória.

## Exemplo

Veja `exemplos/entregas_tipadas.rts`, que registra entregas, mede quantidade,
consulta uma lista emprestada e lê um registro por valor.

## Restrições

- Listas dinâmicas de registros aceitam `adicione` e atribuição por índice
  com variável do mesmo tipo; não é permitido passar um retorno de função
  composto diretamente como argumento de `adicione`.
- O acesso a campos diretamente por `entregas[0].codigo` não está disponível.
  Copie o registro a uma variável e então consulte ou edite seus campos.
- O empréstimo é somente para leitura e existe apenas como parâmetro de função.
- Não há transferência implícita de propriedade por passagem nem por retorno
  de função.
- Não há suporte a listas dinâmicas de textos dinâmicos, empréstimos
  armazenados, referências mutáveis ou estruturas com recursos alocados
  internamente.
- O compilador é experimental e ainda não passou por auditoria de segurança.

## Validação

A suíte nativa cobre Windows e Linux e testa erros de tipos, limites de índice,
crescimento, cópia de registros, campos aninhados, liberação e transferência.
