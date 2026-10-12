# RS 0.22 — Propagação de valores entre blocos

## Vocabulário oficial em português brasileiro

A documentação e as mensagens do RoteiroSimples priorizam termos em português brasileiro. A sintaxe do código usa palavras sem acentos (`inicio`, `senao`, `seja`, `inteiro`, `logico`, `leia`). Textos entre aspas, comentários e explicações podem conter acentos.

| Conceito | Nome adotado |
|---|---|
| *Control-flow graph* | Grafo de fluxo de controle |
| *Basic block* | Bloco básico |
| *Dataflow analysis* | Análise de fluxo de dados |
| *Memory SSA* | Memória versionada em atribuição única |
| *Phi node* | Nó de junção de versões |
| *Constant propagation* | Propagação de valores conhecidos |
| *Dead store elimination* | Eliminação de escritas sem efeito |
| *Bounds checking* | Verificação de limites |
| *Backend* | Gerador de código nativo |
| *Benchmark* | Medição de desempenho |
| *Heap* | Região de alocação dinâmica |
| *Stack* | Pilha de execução |

Os nomes internos antigos e os parâmetros de linha de comando anteriores permanecem como nomes de compatibilidade. Não exigimos que programas antigos sejam reescritos.

## Implementado em `-O 8`

1. O compilador constrói o grafo de fluxo de controle e valida as dependências da memória versionada.
2. Para cada bloco, calcula as posições das listas locais com valores **comprovadamente conhecidos**.
3. Ao encontrar vários predecessores, mantém um valor conhecido **somente se todos os caminhos que chegam ao bloco concordarem**.
4. A análise continua até estabilizar, inclusive quando existem laços.
5. Leitura de uma posição literal comprovadamente válida pode ser substituída pelo valor conhecido.
6. Escrita literal do mesmo valor, em posição válida e sem cálculo com efeitos, pode ser omitida.
7. Índices variáveis, escritas externas e situações desconhecidas invalidam apenas as posições ou objetos que podem ter sido alterados.

A otimização não move operações nem troca a ordem de leitura e impressão. Ela é aplicada depois das transformações conservadoras da RS 0.21 e usa o gerador seguro de código nativo das listas. Os níveis `-O 0` a `-O 7` permanecem disponíveis.

## Exemplo de junção

```text
inicio {
    seja notas: lista[2]
    seja escolha = 0
    leia(escolha)
    se escolha {
        notas[0] = 15
    } senao {
        notas[0] = 15
    }
    escreva(notas[0])
}
```

Mesmo sem conhecer o resultado de `leia`, os dois caminhos atribuem 15 a `notas[0]`. O compilador pode substituir a última leitura por `15`.

Se um caminho atribuir `16`, a leitura permanece na execução. Se houver um índice inválido, uma entrada do teclado ou uma expressão que possa falhar, a transformação conserva as verificações e a ordem dos efeitos.

## Limitações e segurança

- A prova de equivalência funciona para **listas locais de inteiros, índices literais válidos e valores inteiros constantes**.
- A análise considera cada lista independente, porque o RoteiroSimples ainda não tem referências ou ponteiros que permitam dois nomes para a mesma região de memória.
- Os valores dos índices variáveis não são calculados antecipadamente nesta versão.
- Escritas em listas dentro de laços são consideradas na análise de estabilização. Se o valor puder variar entre iterações, a substituição é proibida.
- **Não há garantia geral de segurança de memória**, alocação dinâmica ou referências emprestadas; essas funcionalidades ainda precisam ser projetadas, implementadas e testadas.
- O tamanho menor do executável não prova que todos os programas ficarão mais rápidos. Tempo e consumo de memória precisam de medições separadas.

## Como executar

No Windows:

```powershell
py -3 compilar.py exemplos\memoria_entre_blocos.rts --alvo windows -O 8 --mostrar-ir --mostrar-memoria-versionada -o roteiro_windows.exe
.\roteiro_windows.exe
```

No Linux:

```bash
python3 compilar.py exemplos/memoria_entre_blocos.rts --alvo linux -O 8 -o roteiro_linux
./roteiro_linux
```

Os parâmetros antigos `--mostrar-memory-ssa`, `--salvar-memory-ssa` e `--mostrar-cfg` continuam aceitos por compatibilidade.
