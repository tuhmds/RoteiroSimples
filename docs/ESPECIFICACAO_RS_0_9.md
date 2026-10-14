# Especificação provisória — RoteiroSimples RS 0.9

Documento histórico da 0.9. A referência atual de sintaxe, tipos, propriedade
e limites está em [A linguagem RoteiroSimples](LINGUAGEM_RS.md).

**Contrato de compatibilidade**, não uma gramática definitiva.

Código-fonte: arquivos `.rts`, comandos e identificadores ASCII **sem acentos**. Strings, comentários e mensagens podem usar UTF-8.

## Estrutura

```text
[inclua matematica]
inicio {
    ... instruções por linha ...
}
```

A importação opcional `inclua matematica` precede `inicio`. Comentários `//` são aceitos fora de strings e `;` no fim da instrução é opcional.

Declarações: `seja nome = expressao`, `seja nome: inteiro = expressao` ou `seja nome: logico = expressao`.
São exigidos inicialização e tipos compatíveis. O limite temporário é 256 variáveis de 8 bytes na pilha.

Entrada: `leia(nome)`, apenas destino `inteiro`. Saída: `escreva(expressao)` ou `escreva("texto")`.

Decisão: `se expressao { ... } senao { ... }` (parte `senao` opcional). Repetições: `enquanto expressao { ... }` e `para nome de inicio ate fim [passo N] { ... }`, limite inclusivo, passo inteiro literal não nulo. `pare` e `continue` apenas em laços. `se` e `enquanto` aceitam lógico ou inteiro (zero falso).

Expressões: inteiros de 64 bits, lógicos `verdadeiro`/`falso`, operadores `+ - * / %`, comparações `== != < <= > >=`, parênteses e funções da biblioteca matemática. Comparações geram `logico`; imprimir `logico` ainda mostra 1 ou 0.

## Comportamento e erros

Inteiros têm sinal de 64 bits: de -9223372036854775808 a 9223372036854775807. Soma, subtração, multiplicação e negação com overflow encerram a execução com erro 1. Divisão por zero e divisão do mínimo por -1 também. Divisão trunca em direção a zero. Exceção: overflow ao incrementar contador de `para` termina o laço normalmente.

`-O 0`: sem dobramento de constantes; `-O 1` (padrão): somente constantes seguras, mantendo os erros. `--mostrar-ir` imprime a IR tipada.

Ainda não existem funções do usuário, ponteiros, heap, arrays/listas, objetos, escopo lexical por bloco, CFG/SSA ou backend ARM64. Apenas alvos x86-64 Windows e Linux estão disponíveis e o projeto não é apropriado para produção.
