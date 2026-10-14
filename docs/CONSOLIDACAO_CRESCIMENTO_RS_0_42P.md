# RS 0.42P — consolidação e crescimento da compilação

Este marco mede custos da compilação e corrige a compactação de saltos. Não
altera a sintaxe, os níveis O0–O8, a convenção das funções, os formatos PE/ELF
nem o contrato experimental de propriedade e persistência.

## Compilação completa e etapas

`python -m benchmarks.crescimento` gera entradas válidas e usa um processo
Python novo por amostra. A preparação dos fontes fica fora do cronômetro.
A compilação medida começa na leitura dos módulos e termina na gravação do
executável, incluindo a preparação de resultados genéricos e a análise
sintática/semântica. O início do processo e os imports iniciais do compilador
ficam fora dessa medida; `processo_ms` os inclui separadamente.

O parâmetro opcional `medidor` de `backend.compilar` aceita
`MedicaoCompilacao`. Sem esse argumento a compilação permanece disponível;
o observador não integra os binários. A verificação compara os bytes com e
sem observação nos caminhos conservador, intermediário e SSA, em PE e ELF.

As etapas disponíveis são:

- `carregar_modulos`, `preparar_resultados` e `analise_sintatica_semantica`;
- `estrategia`, `ir_e_otimizacoes` e `ponte_emissor`;
- `cfg`/`cfg_funcoes`, `ssa`/`ssa_funcoes`, `alocacao_registradores`;
- `preparacao_emissor_funcoes`, `emissao_nativa`, `compactacao_saltos`;
- `montagem_executavel` e `gravar_executavel`.

Uma etapa ausente não foi executada nesse caminho. `ir_e_otimizacoes`
também inclui as análises internas usadas pelas transformações O2/O3/O7/O8;
não representa apenas a construção dos nós. Os nomes não prometem a divisão
de cada algoritmo interno em uma fase independente.

Cada etapa registra `total_ns`, `proprio_ns` e número de chamadas. O tempo
próprio exclui as etapas filhas observadas. Não some os tempos inclusivos
de etapas aninhadas: isso contaria o mesmo intervalo mais de uma vez. São
tempos instrumentados, com o custo do observador; não substituem um perfil
detalhado de cada função Python.

## Amostragem, memória e identidade

Uma rodada inicial aquece caches do sistema e não entra na mediana. Nas
rodadas seguintes a ordem dos casos é embaralhada com semente fixa e as
amostras individuais são preservadas. Cada compilação e validação executa
sequencialmente, sem disputa deliberada entre os trabalhadores.

A ferramenta inicia os trabalhadores com `-I -S`: usa os módulos do projeto
explicitamente, sem site hooks ou cobertura injetada pelo processo pai.
O rastreamento de memória ocorre em outra execução, sem fornecer tempos à
mediana. Essa amostra precisa gerar exatamente o mesmo hash do executável.

`python_pico_bytes` mede as alocações rastreadas depois dos imports iniciais,
conforme [tracemalloc](https://docs.python.org/3/library/tracemalloc.html).
O pico residente é uma medida do processo inteiro, incluindo imports e o
próprio rastreamento. No Windows usa `PeakWorkingSetSize`, em bytes, de
[PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters).
No Linux usa `ru_maxrss` de `getrusage`, convertido de KiB para bytes.
Essas medidas não são equivalentes ao orçamento de memória dos programas RS.

O relatório registra fonte, arquivos, linhas, unidade de crescimento,
hashes de fonte/binário, estratégia efetiva e impedimentos. Um hash do código
do compilador e da ferramenta é conferido no começo e no fim; alteração
durante a campanha impede a conclusão `aprovado`. Na CI também é preservado
`GITHUB_SHA`, que pode representar a revisão de merge de uma PR.

## Dimensões e oráculos

| Família | Unidade aumentada | Comportamento validado |
| --- | --- | --- |
| `instrucoes` | atribuições sequenciais | valor recebido mais quantidade |
| `desvios` | condições e junções | soma definida por comparações com a entrada |
| `funcoes` | funções escalares | chamadas à primeira e última funções |
| `misto` | mesmas funções, mais um registro proprietário | mesma saída matemática, com a estratégia conservadora exposta |
| `modulos` | arquivos importados com funções públicas | chamadas aos módulos primeiro e último |

Os resultados esperados são calculados pelo gerador, sem executar o parser,
IR ou otimizador para obter o oráculo. Cada imagem é executada no sistema
nativo, com entrada em execução para evitar que a validação inteira seja
dobrada em constantes. Os hashes precisam permanecer estáveis entre
amostras do mesmo caso.

A função de documentos de `misto` não é chamada. Sua presença mede o efeito
da elegibilidade global na compilação; o cenário não mede desempenho de uma
aplicação real de documentos. O código de funções e módulos mantém as
chamadas do principal pequenas para variar a quantidade de definições sem
misturar desnecessariamente o crescimento do principal.

## Falhas e alertas

Recusa semântica, erro do compilador, timeout, erro do trabalhador, protocolo
inválido, divergência de execução e divergência entre bytes são estados
distintos. Uma recusa não é automaticamente classificada como limite
intencional: a mensagem e o tipo da exceção precisam ser examinados.

O comando termina com falha quando a campanha não foi aprovada. A opção
`--exploratorio` permite preservar casos falhos e continuar a investigação;
ela não aprova esses casos nem altera a conclusão do JSON. Não é usada na CI.

Razões de tempo acima de duas vezes a razão de tamanho geram alertas para
comparação de pares de casos aprovados da mesma família e nível. Isso inclui
a referência experimental 10 vezes maior / mais de 20 vezes mais lento.
É um sinal de investigação, sem reprovação por tempo na CI. Ruído do sistema,
intervalo de amostragem e mudança da carga precisam ser considerados.

## Compactação de saltos

A versão anterior percorria todos os candidatos para recalcular duas
posições de cada candidato, por passagem. A correção mantém posições
originais em um índice de somas dinâmicas de prefixos. Cada consulta e
atualização custa O(log N), em vez de uma varredura O(N).

A seleção continua na mesma ordem e em ponto fixo. A hipótese do candidato
atual só desconta sua redução quando seu fim precede a posição consultada.
As referências RIP, chamadas e rótulos continuam sendo remapeados. O
remapeamento final por acumulados e busca binária foi conservado.

O custo da seleção por passagem passa a O(N log N), mas a quantidade de
passagens pode crescer. Não se afirma que o algoritmo inteiro ou o
compilador tenham complexidade linear para qualquer programa.

`estatisticas_compactacao` registra candidatos, passagens, avaliações,
consultas e passos do índice. Testes usam limites de trabalho determinísticos,
sem exigir um tempo específico do computador. Uma referência congelada da
RS 0.42O, commit `e79d41c`, compara seleção, bytes, rótulos e referências em
100 layouts aleatórios, incluindo fronteiras e referências que permanecem.
Essa referência é ferramenta de desenvolvimento, não um segundo emissor
usado pelo compilador.

## Reprodução e CI

```text
python -m benchmarks.crescimento --tamanhos 10,50,100 --repeticoes 3 --json relatorios/crescimento.json
python -m benchmarks.crescimento --tamanhos 128,256,512 --familias instrucoes,desvios --repeticoes 2 --timeout 20 --exploratorio --json relatorios/limites.json
python -m benchmarks.saltos --comparar-legado --repeticoes 5 --json relatorios/saltos.json
```

A CI Windows/Linux em Python 3.11 coleta uma campanha pequena de crescimento
(4 e 12 unidades, cinco famílias, O0/O8, duas repetições) e uma comparação de
compactação (128 e 512 saltos, três repetições). As imagens precisam executar
com saída correta; amostras de memória e referências também são conferidas.
Não há promessa de velocidade nem limiar de wall time na aprovação.

O benchmark anterior de execução nativa permanece separado, com suas
rodadas intercaladas e quatro programas de referência. Este marco não
comprova projetos de 100 mil linhas, operação prolongada de servidores,
durabilidade após perda de energia, IR de donos ou seleção por função.
Essas dimensões continuam exigindo contratos e ensaios próprios.
