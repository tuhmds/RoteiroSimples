# RS 0.42L — SSA e alocação nativa por função escalar

## Contrato implementado

A representação de funções da 0.42J e os grafos da 0.42K agora permitem
construir SSA e emitir código alocado para `inicio` e cada função escalar.
Parâmetros são definições SSA na entrada; seus tipos não dependem de uma
atribuição posterior. Retornos leem versões dominadas e seguem diretamente
à saída da função. Chamadas conservam nome, assinatura, ordem dos argumentos,
tipo do resultado e posições de origem.

O contrato permanece do programa completo: inteiros/lógicos, parâmetros,
locais e retornos escalares, com todas as operações representadas pela IR.
Literais de texto podem ser impressos. Registros, donos, empréstimos e arquivos
continuam no caminho conservador. Leitura do teclado em funções continua
rejeitada; leitura no principal continua disponível. Não há FFI nova.

| Nível solicitado, funções elegíveis | Comportamento |
|---|---|
| O0 | Emissão anterior, sem transformações |
| O1 | Dobramento seguro de constantes |
| O2 | Propagação local, emissão anterior |
| O3 | Propagação conservadora entre blocos por SSA; emissão anterior |
| O4 | SSA nativa por corpo com registradores e vagas de pilha |
| O5 | SSA nativa com organização dos blocos |
| O6–O8 | Organização, preferência de alocação nas junções, cópias e saltos compactados |

`nivel_ir` informa o estágio de transformação da IR antes da emissão: até 3
nas funções. `gerador=ssa` informa a alocação/emissão real em O4–O8.
O7/O8 não acrescentam memória versionada nem novas transformações a esse
contrato escalar; podem produzir o mesmo binário de O6. Não existe O9.
O caminho histórico de programas sem funções conserva sua estratégia.

## SSA, validação e constantes

Cada corpo tem nomes versionados, dominadores, fronteiras e junções próprias.
As leituras de argumentos, inclusive chamadas aninhadas, participam da
vivacidade. As interfaces validam unicidade das definições, preenchimento dos
phis, dominância, ordem das definições no mesmo bloco, concordância dos usos
com os argumentos e assinatura das chamadas do programa completo.

Na representação nova de `para`, o resultado do incremento é uma versão
temporária. A atualização do contador ocorre somente no bloco posterior ao
teste de estouro. A saída por estouro usa o valor anterior, inclusive quando
esse valor precisa alcançar uma junção. Retornos dentro do laço não passam
pelo incremento. Trechos inacessíveis não recebem instruções SSA emitidas.

O3 propaga valores quando todos os predecessores concordam. A reescrita
volta à IR somente quando a expressão inteira se torna um literal seguro.
Nenhuma chamada é avaliada pelo compilador, removida ou reordenada.
Divisão por zero, divisão/resto de INT64_MIN por -1 e estouros continuam
falhas em execução, inclusive em argumentos cujo parâmetro não é usado.
Não há propagação de valores entre corpos, expansão de chamadas ou remoção
geral de instruções neste marco.

## Emissão nativa, ABI e quadros

O alocador usa R13/R14/R15 e vagas próprias de cada corpo, com cópias paralelas
nas junções e temporário separado para ciclos. Valores vivos através de uma
chamada sobrevivem à função chamada. Os rótulos de blocos têm prefixo próprio
para o principal e cada função, evitando colisões entre identificadores `b0`.

O montador recebe um emissor por função e conserva prólogos/epílogos,
metadados Windows, cópia de parâmetros e convenção interna RS existentes.
Os argumentos continuam empilhados por valor, da esquerda para a direita,
com orçamento oculto e alinhamento contabilizados. O resultado escalar
permanece em RAX. A função não confunde suas variáveis com as do chamador.

No Windows, o prólogo já preserva os registradores usados pela SSA.
No Linux, registradores alocados são guardados em vagas do quadro antes
do corpo e restaurados na saída comum, sem alterar RAX. Isso também vale
para recursão e chamadas mútuas.

As casas dos parâmetros ficam separadas da região SSA, do temporário de
cópias, dos salvamentos Linux e do orçamento oculto. O relatório de alocação
mostra vagas da região SSA; a emissão acrescenta as casas e reservas auxiliares
ao deslocamento físico no quadro. Nenhum desses valores pode se sobrepor.
O cálculo dos quadros inclui todas as reservas efetivas.

Quadros desse novo caminho usam a sondagem de páginas e o limite acumulado
de 768 KiB já aplicados pelo montador. Por isso a alocação de funções pode
ultrapassar 256 vagas quando houver espaço seguro. O limite histórico de
256 vagas do caminho SSA sem funções permanece. A proteção de pilha ocorre
antes de avaliar/copiar os argumentos de uma chamada inviável, e temporários
pendentes de expressões/chamadas aninhadas entram na conta.

## Diagnósticos e exportação

```text
python compilar.py exemplos/fluxo_funcoes_rs042k.rts -O 8 --mostrar-estrategia --mostrar-ssa --mostrar-alocacao --mostrar-copias-phi --salvar-ssa ssa.json -o fluxo.exe
python compilar.py exemplos/fluxo_funcoes_rs042k.rts --alvo linux -O 8 -o fluxo_linux
```

O exemplo continua imprimindo `39`. A SSA é exportada como `RS 0.42L`, com
`principal` e todas as `funcoes`, assinaturas e marca de recursão. A exportação
é uma representação do programa; consultar SSA em O0 não habilita a emissão
otimizada nesse nível. `--mostrar-alocacao` aceita O4–O8.

Memória versionada de funções continua bloqueada, inclusive nas interfaces
internas que recebem um grafo. Os resumos de efeitos da 0.42K continuam
conservadores e não autorizam mover chamadas ou descartar a guarda de pilha.

## Testes e medições

19 testes novos: 14 portáveis, quatro Windows e um Linux. Incluem parâmetros
no primeiro laço, tipos lógicos, retornos, junções, temporário de incremento,
propagação entre blocos, valores vivos em registradores/pilha, aridades de
zero a 17, chamadas aninhadas e ordem das falhas. Uma função com 270 parâmetros
confronta mais de 256 vagas, quadro maior que uma página e sondagem real.
Alterações propositais na SSA verificam rejeição de usos ocultos, assinatura
incompatível e leitura antes da definição no mesmo bloco.

Um oráculo Python independente verifica 16 programas gerados em todos os
nove níveis: 144 execuções nativas por sistema, com valores vivos em torno
de chamadas. Continuam os oráculos anteriores, incluindo 20 programas com
ramos/laços/retornos em O0–O8 e a campanha estruturada de coleções/arquivos.

Os ensaios Windows usam o PE e metadados realmente emitidos pela SSA,
com saltos compactados. Conferem oito registradores inteiros, dez vetoriais,
RSP, RtlVirtualUnwind e exceções INT3 reais em funções e chamadores. O quadro
grande é chamado por uma função RS, preservando o contrato do hospedeiro de
sentinelas. O ensaio Linux chama código ELF emitido com sentinelas nos seis
registradores não voláteis e compara RSP antes/depois, em processo isolado.

```text
python -m benchmarks.medir --fonte benchmarks/funcoes_escalares_rs042j.rts --repeticoes 17 --json medicao-funcoes.json
python -m benchmarks.medir --fonte benchmarks/funcoes_fluxo_rs042l.rts --repeticoes 17 --json medicao-fluxo.json
```

A CI mantém Windows/Linux × Python 3.10/3.11/3.14, cobertura de linhas/ramos
Python com subprocessos e campanha obrigatória. Funções simples e o novo
benchmark com laço/chamadas dentro de funções usam 17 amostras intercaladas
por nível. O segundo benchmark deve imprimir `30000400000`; o resultado
corresponde à soma calculada independentemente, com 200.000 parcelas.
Saídas, retorno e arquivos são confrontados entre os nove níveis.

No ensaio local Windows, o benchmark simples registrou O0 10,680 ms / O8
10,030 ms; o novo benchmark registrou 10,814 / 10,771 ms. Diferenças pequenas,
inicialização do processo e variação do hospedeiro impedem concluir ganho
universal. Os relatórios conservam todos os tempos e hashes; tamanho do
arquivo ou escolha da SSA não substituem medição.

## Limites e continuidade

Recursos proprietários ainda exigem IR e contratos de memória próprios antes
de receber as mesmas transformações. Memória versionada de chamadas,
alocação recuperável, estado de `resultado[T]`, HIGH_ENTROPY_VA e funções
com leitura de teclado permanecem pendentes. A linguagem e seus executáveis
continuam independentes de LLVM, C, montador externo ou máquina virtual.

A base escalar atende a bibliotecas e futuras partes do compilador em RS.
Um cadastro persistente com dados variáveis e reabertura validada continua
como aplicação para orientar Dados RS e bibliotecas do motor/Studio.
