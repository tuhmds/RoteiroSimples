# RS 0.42R — análises de fluxo conforme o uso

Na 0.42Q a SSA e o exame de gravações mortas chamavam a análise completa de
fluxo. Isso calculava definições que chegam aos blocos, garantias e
diagnósticos sem que essas fases consumissem esses dados. O exame de
gravações mortas também construía dominadores que não utilizava.

## Contratos de análise

| Entrada Python | Dados calculados | Uso |
| --- | --- | --- |
| `analisar_fluxo` | Todos os dados históricos, incluindo definições que chegam, garantias, candidatos a phi e possíveis usos sem definição | Diagnóstico completo e interfaces existentes |
| `analisar_fluxo_ssa` | Usos/definições locais, vivacidade e dominadores | Construção SSA escalar e das funções |
| `analisar_vivacidade` | Usos/definições locais e variáveis vivas na entrada/saída | Exame de gravações constantes mortas |
| `analisar_dominadores` | Conjuntos de dominadores | SSA de memória |

As análises parciais têm tipos próprios: `AnaliseVivacidade` e
`AnaliseFluxoSSA`. Não apresentam campos vazios como se fossem diagnósticos
completos. A análise de dominância retorna apenas seu mapa e não examina
efeitos de instruções. A preparação do grafo é local a cada chamada; não há
cache persistente que possa sobreviver à alteração de arestas.

Os cálculos puros ficam em `compilador/calculos_fluxo.py` e são compartilhados
pelas entradas. Mantêm a ordem histórica dos pontos fixos, o tratamento de
blocos inacessíveis, parâmetros, retroarestas, `pare`, `continue` e o estouro
do incremento de `para`. O algoritmo dos conjuntos de dominadores não foi
substituído neste marco.

`AnaliseFluxo`, `analisar_fluxo`, seus parâmetros e formatos de diagnóstico
continuam disponíveis. Os testes conferem todos os seus campos, JSON e
texto contra a referência anterior. A mudança não introduz sintaxe nova ou
dependências de execução e não amplia o subconjunto elegível da IR.

## Observação e trabalho evitado

Os nomes de etapas da 0.42Q continuam identificando os cálculos efetivamente
executados. Uma etapa ausente não representa uma medida zero: ela não foi
executada naquele caminho. Tempos inclusivos e próprios mantêm o contrato
da observação opcional, agregando todas as chamadas de cada etapa.

Os novos contadores registram chamadas concluídas de
`fluxo_analises_completas`, `fluxo_analises_ssa`,
`fluxo_analises_vivacidade` e `fluxo_analises_dominadores`.

No cenário escalar com condições em O8, a compilação observada faz duas
análises de fluxo para SSA e uma de vivacidade para gravações mortas. Há
duas construções de dominadores, em vez de três, e não se calculam definições
que chegam, garantias ou candidatos de diagnóstico. A SSA continua colocando
phis reais pelas fronteiras de dominância e vivacidade; a ausência dos
candidatos de diagnóstico não elimina essa etapa.

Na SSA de memória, o pedido de dominância não calcula vivacidade escalar,
definições que chegam ou garantias. Seus próprios efeitos e cadeias de
memória continuam sendo analisados pelo módulo de SSA de memória. A
observação fina desse módulo ainda não foi ampliada: algumas chamadas
internas permanecem dentro das etapas de otimização de memória existentes.

## Equivalência e referência

`testes/fixtures/fluxo_rs042q.py` congela os corpos de análise completa,
construção SSA e otimização da 0.42Q, commit `47eb322`. Tipos e auxiliares
sem alteração semântica são compartilhados. É uma referência delimitada
para estas alterações, não um segundo compilador independente.

Os testes conferem as projeções contra a análise completa e comparam fluxo,
JSON, texto, SSA e IR em 64 programas gerados. Incluem laços, junções,
parâmetros, retornos e código inacessível. Há comparação PE/ELF em O0–O8,
incluindo listas fixas, funções e possíveis falhas aritméticas. Os testes
impedem explicitamente que uma projeção execute os cálculos não consumidos,
conferem mudanças de grafo e fechamento da observação quando há exceção.

Essas verificações demonstram equivalência nos casos ensaiados, não todas
as combinações possíveis de programas RS.

## Reprodução e CI

```text
python -m benchmarks.crescimento --tamanhos 128,256,512 --familias desvios --niveis 0,8 --repeticoes 3 --timeout 30 --json relatorios/crescimento-desvios.json
python -m benchmarks.analise_ssa --referencia rs042q --tamanhos 32,128,512 --repeticoes 5 --json relatorios/analise-ssa.json
```

A campanha de crescimento continua medindo leitura até gravação,
executando as imagens com oráculo independente e coletando memória em
amostra separada. Comparações completas antes/depois precisam conservar
códigos medidos, fontes e amostras; rodadas consecutivas são sujeitas a ruído.

O benchmark de análise intercala construção e otimização atual/anterior
sobre a mesma IR preparada. Preparação, formatação e conferência ficam fora
do cronômetro. A referência escolhida, seu commit, os hashes de código e de
ferramenta/referência ficam registrados; mudança durante o ensaio o invalida.
O padrão `--referencia rs042p` permanece disponível para reproduzir a
comparação histórica da 0.42Q.

A CI Windows/Linux em Python 3.10/3.11/3.14 mantém os testes existentes.
Em 3.11 guarda a comparação intercalada contra a 0.42Q com 32/128 condições
e três amostras, junto de cobertura, campanhas e benchmarks nativos.
Não há gate de velocidade ou de memória baseado no computador da CI.

## Limites

Os conjuntos de dominadores continuam podendo consumir espaço quadrático.
Selecionar análises evita trabalho sem uso, mas não comprova complexidade
linear ou projetos de 100 mil linhas. O pico Python e o pico residente são
do compilador, não do programa RS; o residente inclui imports e rastreamento.
A análise completa ainda tem os custos necessários a seus diagnósticos.
Seleção por função, IR de proprietários, motor, banco de dados, RS Studio e
autocompilação continuam exigindo etapas próprias.
