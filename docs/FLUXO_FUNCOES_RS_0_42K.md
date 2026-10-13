# RS 0.42K — Fluxo e efeitos por função escalar

## Escopo

A IR iniciada na 0.42J agora oferece CFG e fluxo de dados para `inicio` e
para cada função escalar. Parâmetros são definições na entrada; `retorne`
lê o valor retornado e vai diretamente à saída da própria função. Ramos,
laços, `pare`, `continue` e retornos antecipados conservam suas arestas.
Trechos posteriores a um retorno continuam no relatório como inacessíveis.

O contrato continua restrito a programas compostos por inteiros/lógicos e
funções com parâmetros, locais e retornos desses tipos. Registros, donos,
empréstimos e arquivos conservam sua estratégia anterior. A leitura do
teclado dentro de funções permanece rejeitada pelo parser; a análise não
amplia a sintaxe. A leitura no `inicio` continua disponível.

As análises não transformam chamadas nem o código emitido. Funções usam
O0 sem transformações, O1 com dobramento seguro e O2–O8 com propagação
local e nível IR efetivo 2. Emissão PE32+/ELF64, ABI, desenrolamento,
sondagem/orçamento de pilha e propriedade continuam com seus contratos.

## Grafos separados e retornos

`construir_cfg_programa` retorna um grafo principal e um por função.
`construir_cfg_funcao` exige uma `FuncaoIR` com assinatura escalar compatível
com os tipos dos parâmetros e valores retornados. Uma função que possa
chegar à saída sem retornar um valor é rejeitada nessa interface.

A interface histórica `construir_cfg` conserva o contrato de grafo único:
rejeita um programa com funções para evitar produzir somente o grafo do
`inicio`. Para analisar um corpo isolado com retornos, use a função explícita
que recebe a assinatura. SSA, alocação e memória versionada de funções
permanecem rejeitadas, inclusive quando um grafo é passado diretamente às
interfaces internas. Chamadas no principal também impedem sua conversão SSA.

Na análise nova, `para:incremento` lê o contador e possui uma saída
`estouro_incremento`. O contador é definido em um bloco posterior separado,
`para:gravar_incremento`, alcançado somente se a soma não ultrapassar 64 bits.
Isso acompanha o teste emitido antes da gravação, inclusive para passos
negativos e `continue`. Estouro do incremento encerra o laço normalmente.
O caminho SSA histórico mantém sua representação e emissão anteriores.

Esses grafos descrevem controle normal e retornos. Falhas fatais são
registradas nos efeitos; não recebem uma aresta de exceção separada.
As chamadas não são expandidas dentro do grafo do chamador.

## Fluxo de dados e definições garantidas

Cada grafo calcula usos/definições, definições possíveis que chegam ao bloco,
valores vivos, dominadores e candidatos a junção. Os parâmetros produzem
definições estáveis na entrada, sem avisos de uso antes da definição.
Corpos distintos conservam nomes locais separados, inclusive sombreamento.
Retornos não passam pelas instruções posteriores nem pelo incremento do laço.

A análise distingue definições **possíveis** de definições **garantidas em
todos os caminhos**. Estas usam interseção entre predecessores alcançáveis
até um ponto fixo. Assim, uma definição em somente um ramo não oculta um
possível uso sem definição no outro. Blocos inacessíveis não contaminam
essas informações. A análise apresenta avisos, sem eliminar instruções.
Os candidatos a junção ainda não são uma SSA de funções construída.

## Resumos de efeitos e chamadas

Os efeitos observáveis são resumidos por função sobre seus blocos alcançáveis.
Um ponto fixo propaga efeitos entre chamadas, inclusive recursão direta e
mútua. Saída, entrada representada na IR, possível falha, controle e efeitos
desconhecidos são conservados. Operação nova ou chamada sem corpo conhecido
permanece desconhecida e capaz de falhar.

Locais do callee não se tornam leituras/escritas de locais homônimos do
chamador. `retorne` encerra o corpo chamado; não encerra o processo nem a
continuação do chamador. Chamadas continuam barreiras de ordenação e podem
falhar pela guarda de pilha, mesmo quando o corpo apenas retorna uma constante.
Os resumos não autorizam remoção, reordenação ou avaliação de chamadas pelo
compilador. A marca de recursão é conservada da análise sintática existente.

Os efeitos de cada fase de `para` são separados: a expressão inicial é lida
na entrada do laço, a expressão limite na condição, o contador no teste do
incremento e a gravação ocorre somente no bloco de atualização. A presença
de uma chamada no limite não implica executá-la na fase de incremento.

## Uso e exportação

```text
python compilar.py exemplos/fluxo_funcoes_rs042k.rts -O 8 --mostrar-cfg --mostrar-fluxo --mostrar-efeitos --salvar-cfg fluxo.dot --salvar-fluxo fluxo.json --salvar-efeitos efeitos.json -o fluxo.exe
python compilar.py exemplos/fluxo_funcoes_rs042k.rts --alvo linux -O 8 -o fluxo_linux
```

O exemplo imprime `39`. O DOT reúne subgrafos com identificadores próprios
para `inicio` e cada função. As chamadas aparecem na análise como dependências,
sem misturar arestas de retorno entre funções.

O JSON de fluxo de programas com funções usa versão `RS 0.42K`, com
`principal` e `funcoes`; cada função inclui parâmetros, tipo de retorno,
marca de recursão, dependências, efeitos e blocos. O relatório de efeitos
também publica os resumos e as barreiras completas. A análise histórica de
fluxo sem funções mantém versão `RS 0.11`, acrescentando as definições
garantidas à informação anterior.

## Investigação dos tempos de laços

O relatório Linux da 0.42J continha o mesmo hash de binário em O6/O7/O8,
mas medianas de 3,703 / 5,709 / 5,718 ms. Como esses níveis emitiram os mesmos
bytes, a diferença entre eles não demonstra uma instrução mais lenta de O8.
Isso não determina a causa ambiental exata nem resolve a comparação com O0,
que emite outro binário.

O medidor agora compila todos os níveis antes de medir e executa uma rodada
com cada nível, em ordem embaralhada por semente fixa. A primeira rodada
aquece todos os níveis; as demais são intercaladas. JSON conserva a semente,
ordem de todas as rodadas, tempos individuais, hashes e equivalência de saídas,
códigos e arquivos. Cada processo recebe um diretório vazio. A CI amplia o
benchmark de laços para 17 amostras por nível, nos dois sistemas.

```text
python -m benchmarks.medir --repeticoes 31 --semente 420110 --json medicao-lacos.json
```

O ensaio local Windows com 31 amostras produziu medianas de 15,372 ms em O0
e 15,321 ms em O8; O6/O7/O8 ficaram próximos. Tempos incluem a inicialização
do processo e variam com o hospedeiro. Esse resultado não comprova um ganho
de desempenho nem identifica todas as causas da medição anterior.

## Verificação e continuidade

São 25 testes novos: 22 de fluxo/funções e três do medidor. Incluem parâmetros,
sombreamento, ramos, laços, retornos, instruções inacessíveis, definições
garantidas, resumos transitivos, recursão, bloqueios de SSA e exportação.
Um oráculo Python independente confronta 20 programas gerados em todos os
nove níveis, totalizando 180 execuções nativas por sistema. Outros cenários
preservam entrada, ordem das falhas, limites de 64 bits e orçamento de pilha.
Os testes verificam igualdade dos binários antes/depois da análise em PE/ELF.
Uma falha injetada em um binário real verifica a rejeição de saídas divergentes
pelo medidor. A suíte anterior mantém ensaios nativos de ABI, desenrolamento,
heap, propriedade e arquivos. CI conserva Windows/Linux e Python 3.10/3.11/3.14,
oráculo de coleções e cobertura Python com subprocessos.

Próximo marco: construir SSA por função com parâmetros e retornos explícitos,
depois preparar a emissão e alocação de chamadas conforme a ABI. Medir ganhos
antes de anunciá-los. Um cadastro persistente em RS continua como aplicação
posterior para Dados RS, bibliotecas do motor/Studio e autocompilação gradual.
IR de recursos proprietários, alocação recuperável, evolução de `resultado[T]`
e HIGH_ENTROPY_VA continuam pendentes.
