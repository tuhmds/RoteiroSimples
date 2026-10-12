# Memory SSA — RoteiroSimples RS 0.20

## O que foi implementado

A RS 0.20 transforma o resumo de efeitos da IR em **dependências de memória com versões SSA**, sobre o CFG tipado. Isto é análise de compilação, sem alterar o executável gerado:

- Cada objeto local `lista[N]` ou `texto[N]` recebe uma **região independente**, como `mem:notas` ou `mem:mensagem`. Não há referências/ponteiros nem alias entre objetos na linguagem atual.
- Leituras indicam qual versão da região utilizam. Escritas **consomem** a versão anterior e geram uma nova (`mem:notas@2`), preservando dependências de leitura-após-escrita e escrita-após-escrita.
- Convergências de caminhos e cabeçalhos de laço recebem nós `phi` de memória, com a versão fornecida por cada predecessor real do CFG, inclusive arestas de `pare` e `continue`.
- Entrada (`io:entrada`) e saída (`io:saida`) têm versões próprias. Operações que podem falhar têm uma cadeia `efeito:falha`. Uma cadeia **comum** `efeito:ordem` registra toda E/S e possível falha, evitando que futuras otimizações reordenem observações, validações e acessos.
- Há um **verificador** de definição única, preenchimento de `phi`, dominância das versões e dependência obrigatória antes de cada escrita. O relatório e o JSON são determinísticos.
- A Memory SSA pode ser consultada **mesmo quando o programa usa listas e textos**; o comando não ativa os diagnósticos de SSA escalar que ainda não suportam objetos compostos.

Exemplo de sintaxe:

```text
inicio {
    seja dados: lista[3]
    seja mensagem: texto[40]
    copie(mensagem, "Olá")
    para i de 0 ate 2 {
        dados[i] = (i + 1) * 10
        junte(mensagem, ".")
    }
    escreva(mensagem)
    escreva(dados[1])
}
```

No terminal:

```powershell
py -3 compilar.py exemplos\memory_ssa.rts --alvo windows -O 6 --mostrar-memory-ssa --salvar-memory-ssa memoria.json -o roteiro_windows.exe
.\roteiro_windows.exe
```

Linux:

```bash
python3 compilar.py exemplos/memory_ssa.rts --alvo linux -O 6 --mostrar-memory-ssa --salvar-memory-ssa memoria.json -o roteiro_linux
./roteiro_linux
```

O relatório contém, para cada bloco e operação, `usa [mem:objeto=mem:objeto@N]` e `define [mem:objeto=mem:objeto@M]`. `memoria.json` inclui `phis`, `predecessores`, versões, efeitos da operação e caminhos acessíveis.

## Garantias e limites

**Não confundir modelo de dependências com otimização de memória executável.** Nesta versão:

1. As instruções de máquina **não usam ainda os resultados da Memory SSA**. Programas com listas e buffers permanecem no backend seguro de pilha mesmo em `-O 6`.
2. A representação é por **objeto local nomeado**, não por intervalo de endereços. A independência entre regiões é válida porque a linguagem ainda não possui referências, ponteiros, slices nem aliases de objetos. Quando essas funcionalidades forem implementadas, será indispensável uma análise conservadora de aliasing.
3. O nó `phi` indica a versão possível no encontro dos caminhos; ele **não executa cópia de bytes** no programa. Não implica que as duas regiões tenham o mesmo conteúdo nem elimina verificações de limites.
4. A cadeia `efeito:ordem` é conservadora e limita otimizações agressivas; isso é intencional até que existam provas melhores de segurança e testes.
5. A análise tem granularidade por instrução do CFG, não detalha todas as micro-operações dentro da mesma expressão. Como não há reordenação do backend, a ordem interna original permanece preservada.
6. A Memory SSA não é um gerenciador de heap, não fornece análise de propriedade ou de tempo de vida e não evita automaticamente erros de memória não cobertos pelo runtime existente.

## Validação e evolução

A suíte `testes/test_memory_ssa.py` cobre convergências, laços e retroarestas, objetos independentes, E/S, falhas, leituras de índice, UTF-8, buffers, saída JSON, rejeição de `phi` incompleto e execução de exemplo nativo. Os demais testes verificam que a mudança não causa regressões.

Os próximos passos são modelar **aliasing conservador**, efeitos de memória dentro das transformações de otimização e provas para eliminar ou coalescer acessos. Depois podemos integrar gradualmente o backend SSA com memória, sem remover verificações de índices e de capacidade.
