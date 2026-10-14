# RS 0.42Q — custos internos de IR e SSA

A consolidação da 0.42P mostrou crescimento do tempo de compilação em
programas com muitos desvios. Esta etapa detalha a observação das análises e
corrige duas buscas repetidas, sem alterar a sintaxe, as otimizações
permitidas, a ABI ou a seleção do caminho conservador.

## Problemas medidos e correções

O perfil de um programa gerado com 512 condições em O8 encontrou 1.550
chamadas a `GrafoCFG.alcancaveis`, somando aproximadamente 3,52 segundos de
tempo inclusivo **com cProfile**. A compilação nessa execução instrumentada
levou aproximadamente 7,19 segundos. Esses tempos de diagnóstico não são
comparáveis diretamente com os tempos sem profiler.

No exame de gravações mortas, `otimizar_com_ssa` calculava o alcance dentro
do laço de blocos, embora o grafo não fosse alterado. Agora guarda o conjunto
uma vez naquele exame. Trata-se de uma variável local: uma análise de outro
grafo ou de um grafo modificado calcula novamente o alcance. O mesmo cuidado
foi aplicado à serialização de diagnóstico de `AnaliseFluxo.para_json`.

A colocação de phi fazia `min(pendentes)` e removia um item a cada rodada.
Para D definições pendentes, essa busca podia examinar D + (D-1) + ... + 1
chaves. A fila mínima usa `heapq`: construção inicial O(D), inserção e
remoção O(log D). Os identificadores de blocos produzidos pela RS têm
ordinal numérico único, e a menor chave continua sendo escolhida primeiro.
As fronteiras permanecem ordenadas; a filtragem por vivacidade e o conjunto
de junções já usadas impedem reinserção duplicada.

O custo total de construção SSA não foi declarado linear. Conjuntos de
dominadores, definições que alcançam os blocos, fronteiras e pontos fixos
ainda podem crescer mais rapidamente que a quantidade de instruções.

## Observação interna

O `medidor` opcional da 0.42P agora percorre `construir_ir`, a otimização
escalar, `construir_ssa` e `analisar_fluxo`, inclusive os corpos das funções.
As APIs anteriores continuam podendo ser chamadas sem esse argumento.
O observador permanece uma ferramenta Python de construção do projeto.

| Grupo | Etapas adicionais |
| --- | --- |
| IR | `ir_cobertura`, `ir_assinaturas`, `ir_conversao`, `ir_conversao_funcoes`, `ir_propagacao_local` |
| Otimizações | `ir_otimizacao_ssa`, `ir_otimizacao_ssa_funcoes`, `ir_otimizacao_memoria`, `ir_otimizacao_entre_blocos` |
| Otimização escalar | `otimizacao_cfg_inicial`, `otimizacao_ssa_inicial`, `otimizacao_constantes`, `otimizacao_identificar_constantes`, `otimizacao_reescrita_ir`, `otimizacao_cfg_vivacidade`, `otimizacao_fluxo_vivacidade`, `otimizacao_identificar_mortos`, `otimizacao_eliminacao_ir` |
| Funções escalares | `otimizacao_ssa_funcoes`, `otimizacao_constantes_funcoes`, `ssa_validacao_programa` |
| Construção SSA | `ssa_fluxo`, `ssa_dominancia`, `ssa_preparacao_phi`, `ssa_posicionamento_phi`, `ssa_renomeacao`, `ssa_validacao` |
| Fluxo de dados | `fluxo_preparacao`, `fluxo_definicoes_alcancam`, `fluxo_vivacidade`, `fluxo_dominadores`, `fluxo_definicoes_garantidas`, `fluxo_diagnosticos` |

Cada nome agrega todas as chamadas durante a compilação. Por exemplo, o
mesmo programa pode analisar fluxo na otimização inicial, na análise de
gravações mortas e na emissão SSA. O número de chamadas torna essa repetição
visível; o relatório não presume que existe apenas uma análise.

`total_ns` é inclusivo; `proprio_ns` exclui etapas filhas observadas. Não
some tempos inclusivos aninhados. A preparação de emissores e análises
internas de memória que não receberam observação mais fina continuam
agrupadas nas etapas existentes. A identificação da variável com `cfg_tipo`
fica em `ssa_preparacao_phi`; os cálculos de idom/fronteiras ficam em
`ssa_dominancia`, separados da construção dos conjuntos de dominadores.

Os contadores `ssa_fila_phi_insercoes` e `ssa_fila_phi_remocoes` somam as
operações de fila das construções observadas. `ssa_fila_phi_picos_somados`
soma o maior tamanho de fila de cada construção; não é o pico global de
memória. `otimizacao_buscas_alcancaveis` conta apenas a consulta local do
exame de gravações mortas, não todas as buscas do compilador.

## Equivalência e limites de trabalho

`testes/fixtures/ssa_rs042p.py` congela os corpos de análise de fluxo,
construção SSA e otimização escalar da 0.42P, commit `3c6acf5`. Os nomes de
entrada foram renomeados para coexistirem com a revisão atual. Os tipos,
leitura de efeitos, formatação e auxiliares sem mudança semântica continuam
compartilhados. É uma referência para estas alterações, não um compilador
independente nem uma prova de correção completa da RS.

Os testes comparam fluxo, dominadores, predecessores, idom, fronteiras,
phis, IR reescrita e imagens nativas. Sessenta e quatro programas gerados
combinam condições, laços, `pare`, `continue` e operadores lógicos. Casos de
funções incluem parâmetros, retornos e código inalcançável. A comparação de
imagens PE/ELF cobre O0–O8 e inclui falhas aritméticas que devem continuar
observáveis.

Os testes de crescimento exigem um número constante de buscas completas de
alcance no otimizador e uma chave numérica por elemento de fila em um caso
sem novas fronteiras. Não usam um limiar de milissegundos. A instrumentação
também precisa conservar imagens e fechar etapas quando uma análise falha.

## Reprodução e CI

```text
python -m benchmarks.crescimento --tamanhos 128,256,512 --familias desvios --niveis 0,8 --repeticoes 3 --timeout 30 --json relatorios/crescimento-desvios.json
python -m benchmarks.analise_ssa --tamanhos 32,128,512 --repeticoes 5 --json relatorios/analise-ssa.json
```

O primeiro comando mede a compilação completa conforme a 0.42P, agora com
as etapas internas. Continua validando execução, estratégia, bytes estáveis
e memória em amostra separada. Para comparar versões completas, registre
ambos os códigos medidos, fontes, sistema e amostras; rodadas consecutivas
antes/depois continuam sujeitas a ruído e não são ensaio intercalado.

O segundo compara construção SSA e otimização sobre a mesma IR preparada.
Intercala os métodos e tamanhos em ordem embaralhada com semente fixa,
descarta uma rodada de aquecimento e conserva as amostras individuais. A
preparação das fontes/IR/CFG, formatação, hashes e conferência ficam fora do
cronômetro. As próprias validações internas de `construir_ssa` integram o
custo do algoritmo, como na referência. Nenhum medidor é usado nessa medida.

O relatório guarda identidade do código, identidade da ferramenta e da
referência, sistema, Python, amostras e hashes de resultados. A conferência
de SSA inclui também dominadores e predecessores. Mudança do código ou da
ferramenta durante o ensaio impede a entrega de um relatório aprovado.
Esse microbenchmark não mede I/O de compilação, programas nativos ou
memória; essas medidas pertencem à campanha de crescimento.

A CI mantém a matriz Windows/Linux em Python 3.10/3.11/3.14. Em 3.11,
acrescenta a comparação intercalada com 32/128 condições e três amostras,
guardando `analise-ssa.json`. Os tempos são evidência, sem gate de velocidade.

## Limitações remanescentes

Registros proprietários ainda podem determinar o gerador conservador para
o programa inteiro. A ponte IR/AST, análises repetidas em diferentes fases
e conjuntos de fluxo/dominadores continuam exigindo investigação. O marco
não comprova projetos de 100 mil linhas, o motor, um banco de dados pronto,
RS Studio ou autocompilação. Ele dá medidas e regressões para avançar nessas
direções sem mudar inadvertidamente programas existentes.
