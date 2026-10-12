# SSA tipada no RoteiroSimples RS 0.12

## O que foi implementado

A análise transforma a **IR tipada** em um grafo SSA real: cada atribuição, `leia` e incremento de `para` ganha uma definição com versão única. Todas as leituras são reescritas para usar a versão que as domina. As junções do CFG recebem nós `phi` com um operando associado a **cada predecessor**; não são apenas avisos `phi?` como na RS 0.11.

- Dominadores imediatos e árvore de dominância derivados do CFG alcançável.
- Fronteiras de dominância para colocação iterada de `phi`, com filtro conservador de vivacidade (*pruned SSA*).
- Renomeação das definições e referências através de pilhas por variável.
- `phi` em decisões, cabeçalhos de `enquanto`, `para` e junções de `continue`.
- Verificação de unicidade de definições, preenchimento dos `phi` e dominância dos operandos em blocos e arestas.
- Suporte aos tipos atuais `inteiro` e `logico`; regiões inalcançáveis são marcadas e não são renomeadas.
- Visualização no terminal e exportação JSON sem alterar o programa original.

## Exemplo de um `phi`

```text
inicio {
    seja x = 1
    seja teste = 0
    se teste {
        x = 2
    } senao {
        x = 3
    }
    escreva(x)
}
```

As atribuições nos ramos recebem versões como `x@1` e `x@2`. Na junção, aparece `x@3 = phi(ramo_verdadeiro: x@1, ramo_falso: x@2)`. A impressão usa `x@3`.

## Uso

```powershell
py -3 compilar.py exemplos\ssa.rts --alvo windows -O 2 --mostrar-ssa --salvar-ssa ssa.json -o roteiro_windows.exe
```

O JSON lista blocos, dominadores imediatos, fronteiras de dominância, expressões renomeadas, versões e os operandos de cada `phi`. `INICIAR_RS.bat` oferece a opção 7.

## Limites e próximas etapas

**Ainda não geramos executáveis a partir da SSA.** O backend continua recebendo a IR anterior; SSA é uma representação de análise validada. Na RS 0.12 não eliminamos instruções nem removemos verificações de estouro aritmético. Não há suporte completo a escopos, funções, ponteiros, heap ou novos tipos. A futura etapa de *lowering* dos `phi` exigirá inserção cuidadosa de cópias nas arestas do CFG e testes de equivalência no Windows e Linux.

A SSA não significa, por si só, ganho de velocidade ou segurança total de memória. Benchmarks serão realizados somente quando houver uma transformação de código executada pelo backend.
