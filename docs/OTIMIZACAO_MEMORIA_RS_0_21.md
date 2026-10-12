# Otimizacao segura de memoria — RS 0.21

## Escopo implementado

A RS 0.21 apresenta o nivel `-O 7`, que consulta a **Memory SSA tipada**
validada antes de substituir leituras de listas por constantes ou suprimir
escritas comprovadamente idempotentes. A transformacao e executada sobre a
IR, antes da geracao das instrucoes nativas x86-64. Programas sem listas
continuam com o backend SSA da RS 0.16; programas com listas usam o backend
seguro de pilha, ainda com verificacoes nativas para acessos remanescentes.

### Condicoes para encaminhar uma leitura

1. O objeto e uma lista local de inteiros com capacidade estatica conhecida.
2. A posicao e um literal inteiro **dentro dos limites**.
3. A Memory SSA confirma que a versao de memoria da leitura e a versao
   atingida pelo ultimo comando de escrita na mesma regiao.
4. Um valor para a posicao e conhecido por sua inicializacao em zero ou
   por uma escrita de constante anterior no mesmo trecho sequencial.
5. Nao ocorreu invalidacao por acesso dinamico ou leitura do teclado.

Uma escrita repetida so pode ser retirada quando tanto o indice quanto o
valor sao constantes conhecidas, o indice e valido e o estado da memoria
foi comprovado. Nao descartamos calculos que possam falhar.

### O que permanece conservador

- Nenhum valor conhecido atravessa `se`, `senao`, `enquanto` ou `para`.
  Dentro de corpos as otimizacoes locais podem ocorrer, mas o estado comeca
  desconhecido a cada analise do corpo.
- Escritas com indices dinamicos invalidam os conhecimentos daquela lista.
- `leia(lista[indice])` invalida o cache da lista, pois a entrada modifica
  um valor apenas conhecido em tempo de execucao.
- Listas diferentes nao compartilham enderecos nem referencias na linguagem
  atual. Isso **nao** seria verdade apos acrescentar aliases: nessa etapa a
  prova tera de ser revista antes de habilitar ponteiros ou emprestimos.
- Nao ha propagacao global de constantes de memoria atraves de nos `phi`,
  nem eliminacao global de stores mortos ou vectorizacao.
- Buffers UTF-8 mantem sua implementacao atual, com capacidade protegida.

## Experimente

```powershell
py -3 compilar.py exemplos\memoria_otimizada.rts --alvo windows -O 7 --mostrar-ir -o roteiro_windows.exe
.\roteiro_windows.exe
```

Para comparar:

```powershell
py -3 compilar.py exemplos\memoria_otimizada.rts --alvo windows -O 6 -o memoria_o6.exe
py -3 compilar.py exemplos\memoria_otimizada.rts --alvo windows -O 7 -o memoria_o7.exe
```

Use `python3 -m unittest discover -s testes -v` para testes de equivalencia
entre `-O 6` e `-O 7`, incluindo Windows e Linux. Tamanho menor nao comprova
velocidade maior: medir tempos de execucao exige carga reproduzivel.

## Proximos passos

Verificar aliasing, detalhar o modelo de efeitos intraexpressao, introduzir
propagacao por blocos com encontro seguro de estados nas juncoes de CFG,
melhorar codegen de acesso de indice literal e estudar heap e referencias
com regras de propriedade/tempo de vida.
