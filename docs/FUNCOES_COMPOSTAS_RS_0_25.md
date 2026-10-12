# RS 0.25 — Funções com valores compostos

Esta etapa acrescenta passagem por valor e retorno nativo de registros, listas de inteiros de tamanho fixo e buffers UTF-8 de capacidade definida.

## Sintaxe e semântica

- Parâmetros: `parametro: Tipo`, `parametro: lista[3]` e `parametro: texto[32]`.
- Retornos: `-> Tipo`, `-> lista[3]`, `-> texto[32]`.
- O valor composto é sempre uma cópia independente. Alterações no parâmetro não modificam a variável original do chamador.
- A capacidade do texto e o tamanho da lista integram o tipo e devem coincidir exatamente.
- `retorne valor` e `retorne criar()` podem devolver um composto; na chamada, o destino é reservado pelo chamador.
- Declarações com inicializador composto: `seja p: Produto = criar()`, `seja x: lista[3] = gerar()`, `seja t: texto[32] = mensagem()`.
- Atribuições entre valores compostos e cópias na declaração são permitidas quando seus tipos coincidem.
- Os campos de registros continuam limitados a `inteiro` e `logico`, sem registros aninhados.

## Limitações atuais

Para passar o resultado composto de uma função para outra, armazene primeiro em uma variável. Chamadas como `calcular(criar())` ainda não são suportadas quando `criar` retorna valor composto. A leitura do teclado permanece restrita ao programa principal: funções podem manipular textos com `copie`, `junte` e `limpe`, mas não executar `leia` nesta etapa. Não existem listas de tamanho variável, empréstimos, referências públicas nem alocação dinâmica.

O backend utiliza uma convenção interna de chamada para a cópia de valores e um endereço de retorno privado, sem expor ponteiros na sintaxe. A passagem e o retorno utilizam as reservas e as verificações de pilha existentes. O projeto permanece experimental: não utilizar em produção.

## Compatibilidade

Mantivemos os níveis `-O 0` até `-O 8` e os comandos antigos. A geração conservadora atende aos recursos novos até que as análises de fluxo sejam ampliadas. Todos os comandos, tipos e identificadores que controlamos estão em português brasileiro e sem acentos; mensagens e documentação podem ter acentuação normal.
