# RS 0.40D — Modelo comum de efeitos e propriedade

## Objetivo

A RS precisa registrar os efeitos observáveis de cada operação antes de ampliar as otimizações a arquivos, listas dinâmicas, bytes e funções. A versão 0.40D implementa um **modelo de análise**, sem ativar reordenação nova no gerador nativo.

## Contrato compartilhado

O módulo `compilador/contrato_efeitos.py` contém `Efeitos`. A classe é usada tanto em `compilador/efeitos.py` (análise IR antiga) quanto em `compilador/efeitos_programa.py` (análise moderna da AST).

Os campos do contrato são: `leituras`, `escritas`, `entrada`, `saida`, `pode_falhar`, `arquivos`, `propriedade`, `encerra`, `controle` e `desconhecido`. Há também `barreira_de_reordenacao`, derivada dos efeitos.

O formato JSON antigo de memória versionada foi preservado. O novo relatório usa a versão `RS 0.40D`.

## Segurança de transformações

`podem_trocar_de_ordem(a, b)` recusa a permutação quando há dependência de leitura/escrita, possibilidade de falha, E/S, arquivo, mudança de propriedade, alteração de fluxo ou operação desconhecida.

Essa verificação é conservadora e **não demonstra que uma transformação real seja segura**. O compilador ainda não a utiliza para movimentar ou eliminar instruções. Chamadas de funções são tratadas como potencialmente impuras até existir análise interprocedural confiável.

O modelo registra eventos como `abrir:recurso`, `fechar:recurso`, `mover:lista` e `liberar:lista`. Ele não substitui a verificação semântica de propriedade nem implementa isolamento de banco de dados.

## Comandos de diagnóstico

Exibir efeitos também para programas que usam o gerador conservador:

```text
python compilar.py exemplo.rts --alvo linux -O 8 --mostrar-efeitos-do-programa
```

Exportar o relatório JSON:

```text
python compilar.py exemplo.rts --alvo windows --salvar-efeitos-do-programa efeitos.json
```

Os relatórios usam português brasileiro e incluem comandos em blocos e funções. As opções antigas `--mostrar-efeitos` e `--mostrar-memoria-versionada` permanecem disponíveis para programas suportados pela IR.

## Testes e limites

A suíte testa independência de operações escalares, dependências de dados, falhas aritméticas, comandos desconhecidos, chamadas, arquivos, propriedade de listas, funções, relatório JSON, compatibilidade com memória versionada e execução nativa de O0 a O8 em Windows/Linux.

A análise não é uma prova formal de pureza, ausência de alias ou equivalência semântica. Não introduz dependência obrigatória de execução em C, LLVM ou Python; o compilador ainda é desenvolvido em Python, mas os executáveis continuam nativos e independentes dele.

## Próximo passo

Completar o modelo de efeitos interprocedurais e empréstimos, com testes de alias, antes de habilitar otimizações que afetem propriedade e arquivos. Prosseguir também com o endurecimento de executáveis ELF e PE, incluindo ASLR e proteções de memória.
