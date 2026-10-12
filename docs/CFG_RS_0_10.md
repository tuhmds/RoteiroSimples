# CFG e origem do código — RoteiroSimples RS 0.10

## Alcance desta versão

O front-end associa localização `(linha, coluna)` (ambos a partir de 1) aos tokens e nós da AST. Para não quebrar o backend existente, `NoInstrucao` e `NoExpressao` são subclasses de `tuple` compatíveis com a estrutura da RS 0.9, acrescentando o campo `.origem`. A IR tipada guarda a localização opcional, inclusive após otimização conservadora de constantes.

O CFG representa **um comando por bloco**, por enquanto. Essa forma é correta como grafo, mas ainda não maximiza sequências lineares em blocos básicos grandes. Não é uma implementação de SSA nem um otimizador que muda o fluxo executado.

### Relações no CFG

- `entrada -> instrução ... -> saida`: percurso sequencial.
- `se`: duas arestas rotuladas `verdadeiro` e `falso`, convergindo após os blocos.
- `enquanto`: condição de entrada, corpo que retorna à condição, saída em falso.
- `para`: inicialização, teste do limite, corpo, incremento e retorno ao teste. A IR ainda recalcula o limite a cada iteração, conforme o backend atual.
- `continue` em `enquanto` vai à condição; em `para` vai ao incremento.
- `pare` interrompe **apenas o laço mais interno**, inclusive em laços aninhados.
- Instruções posteriores a saltos incondicionais aparecem como **inalcançáveis**; o DOT as mostra com linha tracejada. Nenhum código é eliminado nesta versão.

### Exibição

```powershell
py -3 compilar.py exemplos\fluxo.rts --alvo windows --mostrar-ast --mostrar-cfg --salvar-cfg fluxo.dot
```

O DOT gerado segue a sintaxe Graphviz. Para renderizar **opcionalmente** (Graphviz instalado):

```powershell
dot -Tpng fluxo.dot -o fluxo.png
```

Os usuários que não instalarem Graphviz podem ler o CFG em texto no PowerShell. O compilador RS não depende do Graphviz.

### Segurança e compatibilidade

Nenhum ponteiro, heap, SSA ou alocador de registradores foi adicionado. A emissão x86-64, as verificações de estouro e a distinção entre `inteiro` e `logico` continuam idênticas à RS 0.9. A suíte executa comparação SHA-256 de 36 binários de referência (RS 0.8) e testes nativos em Linux/Windows.

Limitação de diagnóstico: erros léxicos, instruções desconhecidas e expressões (incluindo alguns erros de tipo) possuem coluna. Algumas mensagens estruturais mais amplas, como falta de fechamento do programa, ainda não identificam uma coluna específica.

**Próxima etapa:** delimitar blocos básicos maiores e estudar análise de fluxo de dados/SSA, sempre com testes de equivalência antes de habilitar otimizações.
