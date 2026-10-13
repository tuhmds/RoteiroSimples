# RS 0.42J — Consolidação, medições e funções escalares na IR

## Escopo implementado

Este marco amplia a verificação da linguagem e inicia a representação
intermediária de funções. Mantém emissão direta PE32+/ELF64, descritores,
propriedade, empréstimos, ABI, proteção de pilha e auxiliares existentes.
Não cria um nível de otimização nem exige ferramenta adicional para executar RS.

## Funções escalares na representação intermediária

Programas compostos exclusivamente por inteiros/lógicos e funções com
parâmetros, locais e retornos desses tipos agora passam pela IR tipada.
`FuncaoIR` conserva assinatura, corpo, deslocamentos e marca de recursão.
`chamada` contém o nome, argumentos ordenados e tipo do retorno; `retorne`
é uma instrução de controle. A tradução de volta preserva a posição da fonte.

```text
funcao calcular(numero: inteiro) -> inteiro {
    seja fator = 3 + 4
    seja ajuste = 9 * 2
    retorne numero * fator + ajuste
}
inicio {
    escreva(calcular(6))
}
```

O resultado é `60`. O1 dobra constantes seguras; O2 propaga constantes
localmente, inclusive em argumentos e retornos. Nenhuma chamada é avaliada
pelo compilador, eliminada ou reordenada. Divisão por zero, divisão de
INT64_MIN por -1 e estouros preservam a falha em execução.
Chamadas são barreiras de efeito desconhecido e possível falha.

| Programa | O0 | O1 | O2–O8 |
|---|---|---|---|
| Somente escalares com funções elegíveis | IR sem transformações | IR com dobramento | IR com dobramento e propagação local; nível efetivo 2 |
| Escalares antigos sem funções, elegíveis | Caminho histórico | Caminho histórico | IR/SSA conforme estratégia histórica |
| Registros, donos, empréstimos, arquivos ou função fora do contrato escalar | Conservador | Conservador | Conservador |

O backend SSA com alocação de registradores ainda não recebe chamadas de
funções. `--mostrar-ir`, `--mostrar-efeitos`, `--mostrar-estrategia` e
`--mostrar-cobertura-intermediaria` mostram o suporte real. CFG/SSA,
memória versionada e alocação de funções são rejeitados com diagnóstico;
não é apresentado um grafo parcial como se cobrisse o programa inteiro.
O contrato é do programa completo; uma declaração de registro, mesmo não
utilizada, conserva a seleção conservadora neste primeiro passo.

## Programas gerados e oráculo independente

`verificacao/casos_gerados.py` gera sequências reproduzíveis com semente fixa.
O modelo Python guarda valores e estado dos donos sem chamar o parser, a IR
ou o gerador nativo. Calcula a saída e os bytes esperados dos arquivos.
O executável RS é confrontado com esse modelo em cada nível solicitado.

Operações cobertas: inserção, substituição, retirada com/sem reinserção,
remoção final, limpeza/reuso, movimentação de coleções, liberação,
reativação com dono novo e gravação/reabertura de dados binários.
Os registros têm inteiro, texto UTF-8, bytes e lista de inteiros.
Após cada operação são conferidos tamanho, ordem e conteúdo de todos os
elementos. As nove inserções iniciais exercitam expansão 4 → 8 → 16.

```text
python -m verificacao.campanha --casos 12 --passos 40 --saida relatorios/campanha
python -m verificacao.campanha --casos 64 --passos 80 --saida relatorios/campanha-ampliada
python -m verificacao.campanha --reproduzir relatorios/campanha/falha_42010_O8.json
```

Níveis padrão são O0/O8. `--niveis` permite outros níveis de 0 a 8.
Falhas produzem fonte, semente, operações, esperado e observado em JSON.
O redutor remove blocos de operações e só aceita a redução após reproduzir
a mesma classe de falha. Índices são recalculados pelo modelo para conservar
programas válidos. A redução não promete o menor programa possível nem
identidade da causa entre todos os erros de uma mesma classe.

A campanha é estruturada e limitada ao conjunto de operações definido;
não é fuzzing guiado por cobertura de todo o compilador. A primeira geração
encontrou uma forma de gravação com campo composto que o parser ainda não
aceita. O caso foi reduzido a uma operação; o gerador passou a mover o campo
para uma variável antes de gravar, usando a sintaxe atualmente suportada.

No Windows, três sequências adicionais de 72 operações acompanham cada
alocação ativa e sua liberação por interceptação das chamadas reais do
sistema. Detectam dono duplicado, liberação desconhecida e memória restante;
399 alocações fecham com 399 liberações (160/160, 147/147 e 92/92).
Os casos portáveis conferem conteúdo/arquivos; o ensaio de heap isola memória
e não escreve arquivos no repositório. Os testes também preservam registradores.

## Cobertura de execução e matriz Python

A CI executa a suíte nativa no Windows/Linux com Python 3.10, 3.11 e 3.14.
Nos trabalhos 3.11, também executa a campanha obrigatória de 12 programas
com 40 passos e mede linhas/ramos do código Python, incluindo os subprocessos
de compilação. JSON e HTML são publicados como artefatos por sistema.
Qualquer falha da suíte, campanha, medição ou consolidação reprova o trabalho.

`coverage.py` é uma dependência opcional de desenvolvimento, fixada em
`verificacao/dependencias.txt`; não integra a linguagem nem seus executáveis.
A versão adotada exige Python 3.11+ para a medição, conforme a
[documentação oficial](https://coverage.readthedocs.io/en/7.16.2/).
Python 3.10 executa a suíte sem essa dependência. Para medir localmente,
use um ambiente isolado com Python 3.11 ou posterior:

```text
python -m venv .ambiente-verificacao
```

Ative esse ambiente (`Scripts/Activate.ps1` no Windows ou `bin/activate` no
Linux), instale `python -m pip install -r verificacao/dependencias.txt` e rode:

```text
python -m coverage run -m unittest discover -s testes -v
python -m coverage run -m verificacao.campanha --saida relatorios/campanha
python -m verificacao.cobertura --saida relatorios
```

A configuração mede o código Python do repositório e exclui os próprios
testes. O modo de subprocessos requer instalação no ambiente ativo, para
que o mecanismo de inicialização do medidor seja carregado pelos processos
filhos. Relatórios de processos são combinados antes de publicar a cobertura.
Este marco estabelece a primeira linha de base; não impõe um percentual
mínimo sem observar os resultados nos dois sistemas.

Cobertura Python não mede instruções de máquina executadas, segurança do
heap, ABI ou durabilidade dos arquivos. Esses aspectos continuam precisando
dos testes nativos, contadores e falhas injetadas. Não equivale à cobertura
das operações representadas pela IR, que permanece um diagnóstico separado.

## Medições de desempenho

`benchmarks/medir.py` compara O0–O8 por padrão e aceita importações RS.
Registra versão, sistema/Python, hash da fonte e do binário, gerador escolhido,
nível IR efetivo, motivos do fallback, tempo de compilação, mediana,
mínimo/máximo e cada tempo individual. Identifica binários repetidos entre níveis.

```text
python -m benchmarks.medir --repeticoes 7 --json relatorios/medicao-lacos.json
python -m benchmarks.medir --fonte benchmarks/funcoes_escalares_rs042j.rts --repeticoes 7 --json relatorios/medicao-funcoes.json
python -m benchmarks.medir --fonte benchmarks/colecoes_rs042j.rts --repeticoes 7 --json relatorios/medicao-colecoes.json
```

A compilação é separada do tempo do processo nativo. A primeira execução
aquece; cada repetição recebe diretório vazio. São comparados saída, retorno,
erros e hashes dos arquivos produzidos. Programa que encerra com erro não
gera resultado de desempenho válido.

A CI guarda as três medições, com três repetições por nível. Tempo inclui
inicialização do processo e varia com o hospedeiro. Tamanho do executável,
percentual de cobertura ou uma pequena diferença de mediana não demonstram
ganho de desempenho. Coleções ainda produzem o mesmo binário em O0–O8;
as funções escalares agora podem produzir código diferente após as
transformações IR, mesmo quando o tamanho PE arredondado não muda.

## Limites e continuidade

São 25 testes novos: 21 portáveis e quatro ensaios Windows, além da campanha
obrigatória e dos relatórios. O conjunto é reproduzível e não comprova todas
as combinações da linguagem. O crescimento do corpus e novas sementes
podem revelar falhas ainda ausentes desses cenários.

Continuam pendentes SSA/CFG de funções, IR de registros/donos/empréstimos,
recuperação de falhas de alocação, evolução do estado de `resultado[T]` e
investigação de HIGH_ENTROPY_VA. O marco não altera visibilidade ou plano
do repositório para contornar a restrição de proteção de branch do GitHub.

Próximo passo recomendado: representar CFG e efeitos de cada função escalar,
com os parâmetros definidos na entrada e retornos como saídas reais, antes
de aplicar SSA e alocação de registradores às chamadas. As coleções e os
recursos proprietários devem entrar depois, com contratos de memória
explícitos e os oráculos mantidos. Essa base atende às bibliotecas do motor,
Dados RS, Studio e ao futuro compilador em RS.
