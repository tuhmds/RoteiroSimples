# Tipos e memória — RoteiroSimples RS 0.7

Esta especificação distingue cuidadosamente o que funciona do que ainda será projetado. RS 0.7 continua experimental e não deve ser usada em produção.

## Tipos implementados

- `inteiro`: inteiro com sinal de 64 bits, com faixa de -9223372036854775808 até 9223372036854775807.
- `logico`: `verdadeiro` (1) ou `falso` (0).
- Declaração explícita: `seja idade: inteiro = 17`.
- Inferência: `seja aprovado = idade >= 18` infere `logico`; `seja preco = 10` infere `inteiro`.
- Todas as variáveis são inicializadas na declaração. Não há conversão implícita entre `logico` e `inteiro`.
- `+`, `-`, `*`, `/`, `%` e negação unária exigem `inteiro`.
- `==` e `!=` exigem dois operandos do mesmo tipo; `<`, `<=`, `>`, `>=` exigem inteiros. O resultado de uma comparação é `logico`.
- `leia` aceita somente destino inteiro. Contadores e limites do `para` devem ser inteiros.
- Para preservar programas anteriores, condições de `se` e `enquanto` continuam aceitando inteiros (zero = falso).
- Por enquanto, `escreva(logico)` imprime `1` ou `0`, não uma palavra.

## Memória implementada

- Todas as variáveis ocupam slots **de 8 bytes na pilha**, tanto inteiros quanto lógicos. Os offsets são definidos estaticamente pelo compilador.
- Há um limite provisório de **256 variáveis locais** enquanto não implementarmos sondagem de pilha no backend do Windows.
- Não há alocação no heap, referências, ponteiros, listas, objetos, coleta de lixo ou análise de tempo de vida. **Verificação de tipos não significa segurança geral de memória**.
- Literais positivos acima do máximo de 64 bits são rejeitados; o literal negativo mínimo é aceito.
- Adição, subtração, multiplicação e negação em tempo de execução **ainda podem sofrer estouro de 64 bits**, sem diagnóstico. Precisamos definir semântica e testes antes de prometer proteção.

## Próximos trabalhos

1. Definir semântica de overflow e testes de todos os casos de borda.
2. Criar tipos reais e textos com tamanho/capacidade, além de acesso com verificação de limites.
3. Projetar referências seguras com regras de propriedade e tempo de vida; somente depois estudar ponteiros brutos explicitamente inseguros.
4. Introduzir IR tipada para otimizações, medindo tempo e tamanho do código gerado.
5. Implementar buffer para `leia` e melhorar os layouts PE/ELF sem perder compatibilidade.

Comandos e nomes de variáveis continuam sem acentos; mensagens e textos UTF-8 podem conter acentos.
