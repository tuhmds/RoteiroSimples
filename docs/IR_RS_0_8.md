# IR tipada RS 0.8 — contrato e limites

## Pipeline

Fonte `.rts` -> `sintaxe.py` (AST + tipos) -> `ir.py` (árvore tipada imutável) -> dobramento conservador de constantes (`-O 1`) -> tradução ao AST esperado pelo backend -> `codigo_nativo.py` -> PE32+/ELF64 x86-64.

Esta **não é uma IR de blocos básicos/SSA**. O objetivo é isolar a otimização de expressões da emissão de bytes e preservar compatibilidade do backend. Não há regalloc, propagação de constantes entre atribuições, nem análise global de fluxo.

## Semântica dos inteiros

Tipo `inteiro`: 64 bits com sinal; faixa [-9223372036854775808, 9223372036854775807]. `+`, `-`, `*` e negação de operandos não constantes acionam testes de overflow do processador. Para qualquer operação constante fora da faixa, o otimizador **não** a substitui por literal; mantém a operação com verificação em tempo de execução. `-9223372036854775808` como literal é permitido, mas negar esse valor em execução é erro.

Divisão por zero e `MIN / -1` já resultavam em erro antes desta versão; a nova IR conserva esses erros. Divisão inteira trunca em direção a zero, inclusive o resto do dividendo. A atualização do contador implícito de `para` **não produz erro** ao transbordar: termina o laço (regra existente que permanece).

Em caso de erro aritmético, o programa retorna código 1. O Linux escreve o diagnóstico em stderr e o Windows continua escrevendo em stdout até que o backend ganhe stderr próprio.

## Níveis

- `-O 0`: sem dobramento de constantes; não desativa verificações de erro, nem codificação curta de imediatos já existente.
- `-O 1`: padrão; dobra operações inteiramente constantes que não têm erros, sem alterar a ordem de avaliação ou de efeitos de entrada/saída.
- `--mostrar-ir`: exibe a representação textual da IR antes de emitir o executável.

## Limitações

Não existe garantia geral de segurança de memória, rastreamento de propriedade, referências, ponteiros ou objetos. A verificação estática de tipos não garante ausência de estouro futuro; as verificações nativas interceptam as operações existentes. O formato PE ainda tem seções limitadas a 4 KiB.

## Validação

`python -m unittest discover -s testes -v` executa comparações entre `-O 0` e `-O 1`, checagem de tipos e programas reais em Windows e Linux x86-64. Medir redução do tamanho do arquivo não equivale a benchmark de velocidade.
