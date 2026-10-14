# RS 0.42O — Operadores lógicos em português

Este marco acrescenta `e`, `ou` e `nao` às expressões da linguagem. O objetivo
é escrever condições cotidianas sem precisar aninhar vários `se`, preservando
tipagem estática, ordem de avaliação e geração direta de executáveis nativos.
O compilador de desenvolvimento continua em Python; o léxico reutilizável
da biblioteca padrão continua escrito em RS.

## Valores aceitos

Os operandos precisam ter tipo `logico`. O resultado também é `logico`.
São aceitos literais, variáveis, comparações e chamadas que devolvam esse tipo.
Não há conversão implícita de inteiro, texto, bytes, lista ou registro para
lógico. Por exemplo, `1 e verdadeiro` e `nao 0` são recusados.

```rts
inicio {
    seja idade = 20
    seja ativo = verdadeiro
    seja permitido = idade >= 18 e ativo
    escreva(permitido)
    escreva(nao permitido)
}
```

`escreva` mantém a representação histórica: verdadeiro aparece como `1`
e falso como `0`.

## Precedência e agrupamento

Da precedência mais alta para a mais baixa:

| Construção | Exemplo |
| --- | --- |
| Aritmética | `quantidade + 1` |
| Comparação | `idade >= 18` |
| Negação lógica | `nao idade >= 18` |
| Conjunção | `ativo e autorizado` |
| Disjunção | `ativo ou autorizado` |

As precedências históricas dentro da aritmética continuam válidas.
Parênteses alteram o agrupamento e tornam a intenção explícita.

| Expressão | Agrupamento equivalente |
| --- | --- |
| `nao idade >= 18` | `nao (idade >= 18)` |
| `a ou b e c` | `a ou (b e c)` |
| `nao a e b` | `(nao a) e b` |
| `(a ou b) e c` | `(a ou b) e c` |

Os operadores binários `e` e `ou` associam da esquerda para a direita.
A expressão `nao a` primeiro obtém o valor de `a` e então o inverte.
Não são acrescentados os símbolos `&&`, `||` ou `!` como alternativas.
O operador histórico `!=` continua sendo comparação de desigualdade.

## Curto-circuito e efeitos

O lado esquerdo é avaliado antes do lado direito, uma única vez.

| Operador | Quando o lado direito é avaliado | Quando é pulado |
| --- | --- | --- |
| `esquerda e direita` | Esquerda verdadeira | Esquerda falsa, resultado falso |
| `esquerda ou direita` | Esquerda falsa | Esquerda verdadeira, resultado verdadeiro |

Uma chamada pulada não executa seu corpo e não produz seus efeitos.
Uma divisão pulada não pode encerrar o programa por divisão por zero.
Essa regra também vale em retornos, argumentos, atribuições e condições.

```rts
inicio {
    seja divisor = 0
    se divisor != 0 e 10 / divisor > 1 {
        escreva("Divisao permitida.")
    } senao {
        escreva("Divisao dispensada.")
    }
}
```

As otimizações O0–O8 precisam preservar quais operandos são executados e
a ordem das chamadas. Por exemplo, `chamada() e falso` ainda precisa executar
`chamada()`; `falso e chamada()` deve pulá-la.

O curto-circuito afeta a execução, não dispensa a análise estática. O compilador
continua verificando nomes, tipos e regras de propriedade de ambos os lados.
`falso e nome_inexistente`, `verdadeiro ou 1` e uma chamada inválida no lado
direito continuam sendo erros de compilação. Os diagnósticos conservam a
posição na fonte para indicar o operando ou a construção recusada.

## Compatibilidade e nomes reservados

Na 0.42N, `e`, `ou` e `nao` ainda podiam ser usados como nomes. Na 0.42O,
essas palavras inteiras, minúsculas e sem acento são reservadas. Renomeie
declarações e seus usos antes de recompilar um programa antigo:

```rts
// Antes: seja nao = falso
inicio {
    seja negado = falso
    escreva(negado)
}
```

Use nomes como `ativo`, `alternativa` ou `negado`. Prefixos não são reservados:
`entrada`, `outro` e `nao_aceito` continuam sendo identificadores normais.
Textos e comentários podem conter as três palavras sem alteração.

## Léxico escrito em RS

`padrao/lexico.rts` acrescenta uma categoria às unidades léxicas sem mudar
o registro `UnidadeLexica`, as posições na fonte ou os diagnósticos existentes.

| Classe | Significado |
| --- | --- |
| 1 | Identificador ou outra palavra reservada, conforme o contrato anterior |
| 2 | Número |
| 3 | Texto |
| 4 | Símbolo simples |
| 5 | Operador duplo, como `>=` e `!=` |
| 6 | Operador lógico de palavra: `e`, `ou` ou `nao` |
| -1 | Caractere não aceito |
| -2 | Texto sem fechamento |

A classe 6 exige a palavra inteira. `outra` permanece classe 1; `"ou"`
permanece classe 3. Consumidores que antes tratavam toda palavra como classe 1
precisam reconhecer a nova classe. A biblioteca preserva offsets em bytes,
linha e coluna; ela não executa análise de tipos nem substitui o parser Python.

## Representações internas e limites

As expressões lógicas têm representação própria na árvore sintática e na IR.
O caminho escalar continua podendo usar as otimizações SSA e a alocação
nativa dos níveis O4–O8. A emissão usa saltos locais para selecionar a
avaliação do lado direito, sem antecipar esse operando.

Neste marco, CFG e SSA mantêm a expressão com curto-circuito dentro da árvore
da instrução. Os desvios internos de cada `e` ou `ou` ainda não aparecem como
blocos separados e valores `phi` no relatório. As análises de efeitos são
conservadoras e incluem ambos os operandos; isso não significa que ambos
serão executados. Registros, donos, empréstimos e arquivos continuam usando
o gerador conservador quando exigido pela estratégia existente.

Não são acrescentados níveis de otimização, reais, decimais, empréstimos
mutáveis nem interfaces do Studio. O motor, Dados RS e a autocompilação podem
usar estas expressões nas bibliotecas e algoritmos seguintes. A futura
camada pedagógica do Studio continua dependente de diagnósticos e serviços
compartilhados do compilador; interpretar intenção em linguagem natural
continua fora deste contrato.

## Exemplo e verificações

[O exemplo completo](../exemplos/operadores_logicos_rs042o.rts) mostra chamadas,
precedência, parênteses e divisão protegida. Sua saída esperada é:

```text
Consulta executada.
1
0
1
0
1
0
Divisao dispensada.
```

Para compilar o exemplo:

```text
python compilar.py exemplos/operadores_logicos_rs042o.rts --alvo windows -O 8 -o logicos.exe
python compilar.py exemplos/operadores_logicos_rs042o.rts --alvo linux -O 8 -o logicos
```

As verificações do marco cobrem precedência, tipos inválidos, palavras
reservadas, operandos pulados com efeitos ou erros e equivalência entre níveis
de otimização. Os testes do léxico em RS comparam classes, limites de palavras
e posições da fonte, incluindo texto, comentários e CRLF. A validação da
entrega deve registrar os resultados reais da suíte e da CI; este contrato
não antecipa contagens nem aprovação de uma execução ainda pendente.
