# RoteiroSimples (RS)

**Linguagem de programação experimental em português brasileiro, com compilação nativa.**

**Versão documentada:** 0.42Q · **Estado:** em desenvolvimento, não indicada para produção.

A **RS** nasceu para tornar a programação compreensível desde o primeiro contato, usando palavras e mensagens em português brasileiro, sem abandonar fundamentos de compiladores, tipagem, gerenciamento de memória e desempenho. Queremos que aprender a programar e construir programas nativos possam fazer parte da mesma jornada.

> **Transparência:** desenvolvemos a RS com apoio intenso de **inteligência artificial** na concepção, implementação, documentação e testes. A IA não é garantia de correção; buscamos revisão humana, testes adversariais e contribuições de pessoas experientes em compiladores. Não afirmamos que o compilador já seja autocompilado ou que a linguagem esteja pronta para uso profissional.

## Navegação

| Precisa de… | Acesse |
| --- | --- |
| Acompanhar os recursos e versões | **[Atualizações e histórico técnico](docs/ATUALIZACOES.md)** |
| Ler os contratos e a arquitetura | [Documentação técnica](docs/) · [Princípios de projeto](docs/PRINCIPIOS_RS.md) |
| Ajudar com correções e funcionalidades | **[Como contribuir (fork, PR e revisão)](CONTRIBUTING.md)** |
| Fazer uma avaliação crítica do compilador | [Convite à revisão técnica](docs/CONVITE_REVISAO_TECNICA_COMPILADOR.md) |
| Acompanhar propostas e trabalhos em andamento | [Pull requests](https://github.com/tuhmds/RoteiroSimples/pulls) · [Questões e propostas](https://github.com/tuhmds/RoteiroSimples/issues) |
| Experimentar a linguagem | [Começar no Windows](#começar-no-windows) · [Compilar no Linux](#compilar-no-linux) · [Exemplos](exemplos/) |

## O que já funciona e o que ainda falta

O **compilador de desenvolvimento**, atualmente escrito em **Python**, lê arquivos `.rts` e gera diretamente executáveis nativos **x86-64** para Windows (PE32+) e Linux (ELF64), sem etapa obrigatória em C, LLVM ou montador externo. O programa compilado **não precisa de Python para executar**, mas utiliza os serviços normais de seu sistema operacional.

Entre as capacidades implementadas em diferentes subconjuntos da linguagem estão tipos e funções, módulos, textos e bytes, listas e registros, propriedade e empréstimos de leitura, efeitos, representação intermediária tipada, CFG, SSA, alocação de registradores e otimizações nativas. **Nem todos os recursos percorrem o caminho otimizado**; a cobertura e as limitações são apresentadas nas [notas técnicas](docs/ATUALIZACOES.md).

**Ainda faltam:** ampliar a linguagem e suas bibliotecas para aplicações reais, consolidar caminhos conservador e otimizado, desenvolver o RS Studio e atingir o objetivo de **autocompilação**, isto é, ter o compilador escrito na própria RS e verificável de forma independente.

## Como colaborar

O caminho preferencial é **criar um fork**, abrir uma ramificação de trabalho e enviar um **pull request** para a `main` deste repositório. Alterações propostas passam por **análise do responsável pelo projeto (`@tuhmds`) antes da incorporação**. Críticas arquiteturais, documentação e testes de falhas são igualmente bem-vindos.

Leia o [guia de contribuição](CONTRIBUTING.md), o [modelo de pull request](.github/PULL_REQUEST_TEMPLATE.md) e as [regras de projeto](docs/PRINCIPIOS_RS.md). A proteção técnica da ramificação é configurada separadamente nas opções do GitHub; estas instruções, isoladamente, não a substituem.

## Histórico detalhado das versões

## RS 0.42Q — Custos internos de IR e SSA

As medições distinguem conversão, propagação local, otimização escalar,
fluxo de dados, dominância, colocação de phi, renomeação e validação.
A eliminação de gravações mortas calcula os blocos alcançáveis uma vez por
grafo; a fila de colocação de phi mantém a ordem mínima usando um heap.
Testes com referência congelada conferem a IR, os nós SSA e as imagens
PE/ELF. A CI guarda uma comparação intercalada de análise com a 0.42P.
[Contrato, medições e limites](docs/ANALISE_SSA_RS_0_42Q.md).

## Histórico: RS 0.42P — Consolidação e crescimento da compilação

As medições agora incluem leitura de módulos, análise sintática e semântica,
IR/otimizações, CFG/SSA, alocação, emissão e gravação do executável. Processos
isolados coletam tempos e uma amostra separada de memória. Geradores de
instruções, desvios, funções, programas mistos e módulos conferem a execução
com um modelo independente; erros e limites continuam visíveis no relatório.

A compactação de saltos usa somas de prefixos em índice dinâmico, preservando
a ordem de seleção e os bytes da versão anterior. A CI guarda medições de
crescimento e comparação com a referência congelada. As curvas não prometem
escalabilidade ilimitada nem ampliam o contrato da IR.
[Contrato, métodos e limites](docs/CONSOLIDACAO_CRESCIMENTO_RS_0_42P.md).

## Histórico: RS 0.42O — Operadores lógicos em português

Expressões agora combinam valores `logico` com `e`, `ou` e `nao`.
`e` avalia o lado direito somente quando o esquerdo é verdadeiro; `ou`
somente quando é falso. A ordem de avaliação preserva chamadas e erros.
Comparações têm precedência sobre `nao`, seguido de `e` e depois `ou`.
Por exemplo, `nao idade >= 18` equivale a `nao (idade >= 18)`.

O compilador verifica os dois lados mesmo quando um deles será pulado na
execução. As três palavras passam a ser reservadas; programas antigos que
as usavam como nomes precisam renomeá-los. A biblioteca de léxico em RS
acrescenta a classe 6 para esses operadores, preservando as classes 1–5.
[Contrato, exemplos, verificações e limites](docs/OPERADORES_LOGICOS_RS_0_42O.md).

## Histórico: RS 0.42N — Retomada coordenada de cadastro em RS

O cadastro experimental agora usa duas cópias alternadas, geração e marcador
de confirmação. Leitores e gravadores cooperantes usam uma trava estável;
uma gravação com geração obsoleta é recusada. A leitura retoma a cópia válida
mais recente quando a outra está incompleta ou corrompida. Formato, seleção,
validação e protocolo de escrita continuam implementados em RS.

`consulte_arquivo` distingue arquivo aceito, ausência e falha sem abrir nem
alterar o arquivo. Três executáveis demonstram inicialização, atualização e
reabertura; os testes encerram processos em etapas da rotina real de escrita.
O marco não oferece ACID nem durabilidade absoluta após perda de energia.
[Contrato, formato, exemplos e limites](docs/RETOMADA_COORDENADA_RS_0_42N.md).

## Histórico: RS 0.42M — UTF-8 explícito e cadastro persistente em RS

A linguagem agora converte texto e bytes explicitamente, com UTF-8 inválido
reportado por estado recuperável e preservação do destino. A biblioteca
`utf8.rts` fornece resultados proprietários para essas conversões.

O cadastro experimental acrescenta, consulta por empréstimo, altera e remove
registros com título e conteúdo binário variáveis. Serialização, validação
com limites e persistência por arquivo provisório são escritas em RS.
Dois executáveis independentes gravam e reabrem o formato RSCV versionado.
Os testes cobrem corrupção, falhas de escrita, propriedade e ABI Windows.
[Contrato, formato, exemplos e limites](docs/CADASTRO_PERSISTENTE_RS_0_42M.md).

## Histórico: RS 0.42L — SSA e alocação nativa das funções escalares

Funções escalares agora têm parâmetros e retornos na SSA e são emitidas
com alocação de registradores em O4–O8. O3 propaga constantes entre blocos,
preservando chamadas e erros. A emissão conserva a convenção interna RS,
ordem dos argumentos, proteção de pilha e metadados Windows; o Linux
acrescenta os salvamentos necessários dos registradores alocados.

`--mostrar-ssa`, sua exportação e `--mostrar-alocacao` agora cobrem essas
funções. A CI inclui ensaios nativos de preservação e desenrolamento e
medições intercaladas de laços/chamadas dentro dos corpos. Registros,
donos, empréstimos e arquivos continuam no caminho conservador.
[Contrato, verificações e limites](docs/SSA_FUNCOES_RS_0_42L.md).

## Histórico: RS 0.42K — Fluxo e efeitos das funções escalares

O compilador agora analisa `inicio` e cada função escalar em grafos separados.
Parâmetros são definidos na entrada e retornos seguem diretamente à saída da
função. A análise cobre ramos, laços, código inacessível, valores vivos e
definições garantidas em todos os caminhos. Resumos propagam efeitos entre
chamadas, inclusive recursão, conservando a verificação de pilha.

`--mostrar-cfg`, `--mostrar-fluxo` e suas exportações agora aceitam esse conjunto.
As funções continuam com nível IR efetivo até 2; SSA/alocação de chamadas
permanecem pendentes. O medidor intercala execuções por semente fixa para
reduzir a influência da ordem temporal na comparação O0–O8.
[Contrato, verificações e limites](docs/FLUXO_FUNCOES_RS_0_42K.md).

## Histórico: RS 0.42J — Consolidação e funções escalares na IR

Programas com somente inteiros/lógicos e funções escalares agora passam pela
representação intermediária tipada. O1 dobra constantes seguras e O2 propaga
constantes localmente nos corpos, argumentos e retornos. O2–O8 usam nível IR
efetivo 2 nesse conjunto; chamadas ainda não recebem alocação SSA.

A consolidação acrescenta programas gerados com modelo independente de
valores/donos/arquivos, reprodução e redução de falhas, cobertura de linhas
e ramos Python com subprocessos e CI Windows/Linux em Python 3.10/3.11/3.14.
As medições O0–O8 registram o gerador efetivo e identificam binários iguais.
[Contrato, verificações e limites](docs/CONSOLIDACAO_RS_0_42J.md).

## Histórico: RS 0.42I — Leitura de registros por empréstimo

Funções com `emprestimo[Registro]` leem os campos de um registro local ou
de `empreste(colecao[indice])`, conservando o elemento na lista. Texto,
bytes, subregistros e coleções aninhadas têm vistas de leitura que podem
atravessar chamadas. O compilador rejeita alteração, descarte, armazenamento
ou retorno do empréstimo e consumo da mesma coleção na árvore de chamada.

A biblioteca de documentos acrescenta busca por título e soma dos tamanhos,
inteiramente em RS. O [exemplo de pesquisa](exemplos/aplicacoes/pesquisa_documentos_rs042i.rts)
consulta e mostra documentos sem retirá-los. Não há alocação de conteúdo;
as palavras e buffers fixos da vista usam temporários contabilizados na pilha.
[Contrato, custos e limites](docs/EMPRESTIMOS_REGISTROS_RS_0_42I.md).

## Histórico: RS 0.42H — Coleções de registros proprietários

`lista[Registro]` agora aceita registros com texto, bytes, listas e subregistros
proprietários. Inserção e substituição recebem `mova(registro)` ou um valor
novo. `retire(colecao, indice)` transfere um registro para fora da lista,
remove sua posição e preserva a ordem. Limpeza, remoção, liberação e saídas
de escopo descartam os campos de cada elemento antes do armazenamento da lista.

Coleções podem ocupar campos de registros, ser aninhadas e atravessar funções
e resultados via registros proprietários. O crescimento preserva os ponteiros
do conteúdo. Registros copiáveis mantêm seu comportamento histórico por valor.
O [exemplo de catálogo](exemplos/aplicacoes/colecao_documentos_rs042h.rts) usa
a biblioteca de documentos em RS. [Contrato e limites](docs/COLECOES_PROPRIETARIAS_RS_0_42H.md).
Leitura de campos de elementos por empréstimo chegou na RS 0.42I.

## Histórico: RS 0.42G — Resultados com propriedade

`resultado[texto]`, `resultado[bytes]` e resultados de registros proprietários
agora transportam donos. `sucesso[T](mova(valor))` recebe o conteúdo sem
duplicá-lo; `falha[T](codigo)` devolve um valor vazio sem alocar conteúdo.
`propague` preserva o código de erro e descarta os donos restantes ao retornar.
Para retirar o valor de um sucesso, use `mova(resposta.valor)`. Resultados de
valores copiáveis mantêm seu comportamento histórico.

A [biblioteca de documentos em RS](biblioteca_padrao/documentos.rts) compõe
validação de título e conteúdo, criação e alteração de documentos com
falhas recuperáveis. O [exemplo](exemplos/aplicacoes/documento_resultado_rs042g.rts)
rejeita uma entrada e continua processando outra no mesmo executável.
[Contrato, testes e limites](docs/RESULTADOS_PROPRIETARIOS_RS_0_42G.md).

## Histórico: RS 0.42F — Registros proprietários em funções

Funções agora recebem e devolvem registros com campos `texto`, `bytes`, listas
dinâmicas e subregistros proprietários. Use `mova(origem)` ou uma chamada que
produza um registro novo. O transporte preserva os ponteiros dos campos;
escopos, retornos e temporários descartam cada dono restante. Registros sem
donos continuam copiáveis por valor. O compilador rejeita consumir campos
sobrepostos ou emprestar um campo e transferir seu registro na mesma chamada.

O [exemplo de documento](exemplos/aplicacoes/documento_registro_rs042f.rts)
exercita criação, alteração, encaminhamento e consumo. O
[contrato e os limites](docs/REGISTROS_EM_FUNCOES_RS_0_42F.md) descrevem as
verificações nativas, incluindo ABI e desenrolamento real no Windows.
Resultados com donos foram acrescentados na 0.42G. Coleções de registros
proprietários ainda dependem de transferência e descarte por elemento.

## Histórico: RS 0.42E — Movimentacao de registros proprietarios completos

A linguagem passou a permitir `mova(destino, origem)` entre registros proprietarios de mesmo tipo, inclusive com texto, bytes, listas e subregistros. O gerador nativo verifica as folhas proprietarias da origem, descarta os antigos donos do destino, movimenta o agregado e inativa a origem. Parametros e retornos foram acrescentados na 0.42F; colecoes de registros proprietarios permanecem pendentes. Implementacao: [PR #9](https://github.com/tuhmds/RoteiroSimples/pull/9).

## Histórico: RS 0.42D — Campos dinamicos com dono em registros locais

A RS passou a permitir campos `texto`, `bytes`, `lista[inteiro]` e `lista[logico]` dentro de registros locais, com gerenciamento automatico de seus descritores e transferencia explicita por `mova`. O transporte do agregado chegou nas revisoes 0.42E/0.42F; copias implicitas e colecoes de registros proprietarios continuam rejeitadas. A implementacao e os testes estao na [PR #8](https://github.com/tuhmds/RoteiroSimples/pull/8), com contrato historico em `docs/REGISTROS_PROPRIETARIOS_RS_0_42D.md`.

## Dados RS — Biblioteca de codificacao binaria (PR #6)

A biblioteca `padrao/codificacao_binaria.rts`, implementada em RS, codifica e le inteiros nao negativos little-endian em blocos de 4/8 bytes, com resultados e falhas recuperaveis. O gravador e o leitor da prova `entregas.rsd` usam o mesmo modulo, com 100 registros verificados entre processos e testes de truncamento/corrupcao. O suporte a valores de 64 bits esta restrito ao intervalo positivo de `inteiro` assinado. Nao ha transacoes, indices, diario de recuperacao ou garantias ACID. [PR #6](https://github.com/tuhmds/RoteiroSimples/pull/6), com detalhes em `docs/DADOS_RS_PROVA_BINARIA_V1.md`.

## RS 0.42C — Biblioteca lexico em RS (PR #5)

O analisador lexico escrito na propria RS pode ser importado com `importe "padrao/lexico.rts" como lexico`. Recebe bytes por emprestimo, devolve `lista[UnidadeLexica]` com offsets na fonte original e diagnosticos recuperaveis (classes -1 e -2), sem encerrar o processo. Tambem expoe o registro copiavel `DiagnosticoLexico` e `obter_diagnostico`, que devolvem codigo, posicao em bytes, linha e coluna sem encerrar a aplicacao. A ferramenta de exemplo usa o modulo; o Studio podera fazer o mesmo. A revisao corrigiu tambem tipos de registros importados dentro de `lista[Tipo]` no resolvedor de nomes. Testes diferenciais com o lexico Python e um processo que examina codigo invalido e valido verificam o comportamento em Windows/Linux. Integrado apos a RS 0.42A.3: [PR #5](https://github.com/tuhmds/RoteiroSimples/pull/5). Consulte `docs/LEXICO_NATIVO_RS_0_42C.md`.

**Linguagem de programação em português brasileiro** com compilador de desenvolvimento
em Python 3.10+ que gera diretamente executáveis nativos x86-64 Windows (PE32+) e Linux
(ELF64), sem etapa intermediária obrigatória em C, LLVM ou montador externo. Os
executáveis gerados **não dependem do Python**. Projeto experimental: **não usar em produção**.

> **Decisão linguística:** palavras reservadas, nomes de variáveis, tipos, funções e caminhos
> que controlamos seguem o português brasileiro e não levam acentos na sintaxe.
> Mensagens, comentários e textos exibidos aceitam acentuação e UTF-8 normalmente.
> Alguns nomes de arquivos e argumentos históricos foram mantidos por compatibilidade.

## RS 0.42A.3 — Bytes dinâmicos

`seja dados: bytes` cria um buffer binário crescente sem capacidade declarada.
`adicione_byte`, leitura e substituição por índice, `copie`, `junte`, `limpe`,
`tamanho` e `capacidade` operam nesse tipo. `bytes[N]` mantém seu comportamento
histórico e aceita cópia/acréscimo explícitos de outros buffers binários.

Funções recebem/devolvem bytes por `mova`; `emprestimo[bytes]` permite leitura
durante chamadas. O transporte preserva o ponteiro, sem copiar conteúdo, e o
descarte é automático por escopo. Comprimentos, índices, valores de 0 a 255 e
aritmética de crescimento são verificados. Arquivos completos podem ser lidos
e gravados com bytes fixos/dinâmicos, preservando NUL e qualquer sequência
binária. Texto UTF-8 e bytes permanecem tipos distintos, sem conversão implícita.

Texto, bytes e listas compartilham o gerenciador de memória; texto e bytes
também compartilham vistas, cópia e carregamento crescente de arquivos. A
biblioteca RS ganha `padrao/binarios.rts`, com cópia, concatenação, comparação
e soma modular. A [aplicação binária](exemplos/aplicacoes/arquivo_binario_rs042a.rts)
constrói, transfere, grava e recupera dados, verifica a igualdade e demonstra
a independência de uma cópia explícita.

A [CI da revisão aprovada](https://github.com/tuhmds/RoteiroSimples/actions/runs/38393807039)
executou 569 testes por sistema, sem falhas: 557 aprovados e 12 ignorados
no Windows; 543 aprovados e 26 ignorados no Linux. Há 42 testes adicionais desde a 0.42A.2,
incluindo dados binários arbitrários, crescimento, transferência,
falhas simuladas e desenrolamento Windows real. Detalhes, provas e limites estão na
[nota técnica](docs/BYTES_DINAMICOS_RS_0_42A_3.md) e na
[revisão conjunta](docs/REVISAO_CONJUNTA_RS_0_42A.md). Os marcos foram organizados
em propriedade 0.42A.1, texto 0.42A.2 e bytes 0.42A.3, com commits preservados.
Donos em registros chegaram nas revisões 0.42D a 0.42F. Coleções de donos,
empréstimos mutáveis e operações posicionais com buffers dinâmicos permanecem pendentes.

## RS 0.42A.2 — Texto UTF-8 dinâmico

`seja nome: texto` cria um texto que cresce sem capacidade fixa declarada.
Leitura, `copie`, `junte`, `limpe`, impressão e persistência nativa operam
nesse armazenamento; `texto[N]` continua disponível. Funções recebem e
devolvem textos por `mova`, com empréstimos de leitura `emprestimo[texto]`.

`tamanho` e `capacidade` são bytes. `caracteres` conta valores escalares
Unicode; `byte_em` consulta um byte com limite verificado. Igualdade entre
variáveis usa o conteúdo UTF-8, sem normalização ou comparação de ponteiros.
Conteúdo externo inválido é rejeitado, sem truncamento para caber no texto.

A memória usa as mesmas rotinas de reserva, crescimento e descarte das
listas, com passo de um byte. A biblioteca em RS ganha `padrao/textos.rts`;
a [aplicação de documento UTF-8](exemplos/aplicacoes/documento_utf8_rs042a.rts)
recebe um nome de comprimento variável, constrói, transfere, grava e
recupera o documento. Os executáveis continuam independentes de Python.

A [CI aprovada](https://github.com/tuhmds/RoteiroSimples/actions/runs/38382667977)
executou 527 testes por sistema, sem falhas: 12 ignorados no Windows e
23 no Linux. Sintaxe, provas e limites estão na
[nota técnica](docs/TEXTO_DINAMICO_RS_0_42A_2.md).
Bytes dinâmicos chegaram na 0.42A.3; donos em registros, na 0.42D a 0.42F.
Coleções de donos e empréstimos mutáveis continuam pendentes.
Esta entrega foi integrada após o marco de propriedade 0.42A.1.

## RS 0.42A.1 — Funções que recebem e devolvem listas proprietárias

Primeiro marco experimental da RS 0.42A: funções podem receber e retornar
`lista[]` e `lista[T]` com transferência explícita de propriedade.
`mova(origem)` passa o dono a uma função, retorno ou declaração nova;
`mova(destino, origem)` continua disponível para destinos já existentes.
O transporte usa somente as três palavras do descritor, sem copiar
os elementos nem alocar outra coleção. Empréstimos continuam restritos
à leitura durante chamadas síncronas.

A biblioteca RS acrescenta cinco funções para consultar e selecionar
listas de inteiros de comprimento variável. A
[demonstração de cadastro numérico](exemplos/aplicacoes/cadastro_pessoas_rs042a.rts)
cria registros, atualiza uma idade, calcula créditos em centavos, grava
um arquivo novo e recupera os dados usando funções com propriedade explícita.

O contrato comum distingue valores copiáveis, proprietários, empréstimos
e recursos de arquivo. Ele acompanha os efeitos das transferências sem
habilitar transformações SSA: esses programas usam o gerador conservador
de `-O 0` a `-O 8`. A entrega inclui verificações de cópia implícita,
consumo duplicado e empréstimo/consumo do mesmo dono numa chamada.

**Escopo:** texto/bytes dinâmicos, donos aninhados, empréstimos mutáveis,
funções genéricas gerais, novos operadores lógicos e números reais ficam
para marcos seguintes. Esta entrega não conclui toda a RS 0.42A.
A proteção de pilha inclui argumentos e temporários das chamadas. A
[integração contínua](https://github.com/tuhmds/RoteiroSimples/actions/runs/38372044241)
executou 487 testes por sistema, sem falhas: 12 ignorados no Windows e
20 no Linux, conforme a plataforma.

[Contrato, exemplos, migração e limites da RS 0.42A.1](docs/VALORES_DINAMICOS_RS_0_42A_1.md).

## RS 0.41.5 — Desenrolamento comprovado pelo Windows

Os testes agora consultam `RtlLookupFunctionEntry` e `RtlVirtualUnwind`
com o código e os metadados reais do compilador. Eles percorrem prólogos
parciais, corpos com operandos temporários na pilha e etapas dos epílogos.
Exceções reais, isoladas em processos de teste, verificam a recuperação
de quadros, oito registradores inteiros e dez vetoriais preservados pela ABI,
sem exigir SDK ou compilador externo.

O ensaio revelou uma falha concreta: salvar `RBX` depois de estabelecer
`RBP` permitia restaurar `RBX` do endereço errado quando havia temporários
na pilha. Os salvamentos agora precedem o estabelecimento do quadro.
Funções Windows preservam os oito registradores inteiros não voláteis,
e os retornos compostos acompanham os novos deslocamentos dos argumentos.

As descrições foram ampliadas para **22 rotinas auxiliares**, incluindo
E/S, cache de entrada, alocação, liberação, fechamento, sincronização,
verificação de arquivos e bloqueio. Epílogos Windows usam sequências
reconhecidas pelo sistema, com validação dos bytes emitidos. A impressão
zera ponteiros nulos completos de 64 bits, e diagnósticos de texto e lista
também são emitidos quando esses tipos aparecem somente em funções.

**Limites:** os blocos fatais que realinham a pilha e encerram o processo
não são rotinas retornáveis cobertas pela tabela. A RS ainda não oferece
um mecanismo próprio de exceções nem garantias formais de segurança.
`HIGH_ENTROPY_VA` continua desativado.

[Ensaios, correções e limites da revisão](docs/DESENROLAMENTO_REAL_WINDOWS_RS_0_41_5.md).

## RS 0.41.4 — Auditoria da ABI e metadados das rotinas auxiliares Windows

Os caminhos fatais no Windows agora alinham a pilha e reservam espaço
de sombra e argumento extra **antes** de chamar `WriteFile` e
`ExitProcess`, mesmo quando o programa não utiliza listas.

Rotinas com prólogos/epílogos compatíveis de arquivos, recursos,
publicação e listas dinâmicas passaram a receber `.pdata`/`.xdata`
**com registro e verificação dos bytes realmente emitidos**.
Prólogos desconhecidos interrompem o registro, em vez de gerar
metadados falsos. Foram adicionados testes de corrupção de prólogo,
saída por erro e funcionamento nativo em Windows.

**Cobertura ainda parcial:** rotinas com salvamento diferente de
registradores e quadros não convencionais precisam de outra descrição.
`HIGH_ENTROPY_VA` segue desativado até investigação e correção de
sua falha de fechamento de arquivo. A linguagem continua experimental.

[Auditoria técnica, verificações e limitações](docs/AUDITORIA_ABI_WINDOWS_RS_0_41_4.md).

## RS 0.41.3 — Sondagem própria e quadros grandes desenroláveis

O gerador Windows agora sonda páginas de guarda em uma rotina folha
inteiramente nativa (`rs_sondar_pilha`), que preserva `RAX` e `RSP`
e usa apenas `R10`/`R11`, registradores voláteis. A reserva final
ocorre em uma única instrução `sub rsp,rax`, representável na
tabela de desenrolamento PE.

Os quadros grandes passam a receber `.pdata`/`.xdata` reais,
incluindo as duas formas de `UWOP_ALLOC_LARGE` quando necessárias.
Os testes verificam prólogos e estrutura PE, além da execução nativa
com quadros grandes, funções, entrada, listas e arquivos em
diferentes níveis de otimização.

**A cobertura ainda não é universal**: rotinas auxiliares precisam de
auditoria própria, e `HIGH_ENTROPY_VA` continua desativado no Windows
até comprovada correção da violação de acesso identificada antes.
O Linux mantém ELF PIE, separação de código e dados e pilha NX.

[Implementação, verificações e limitações](docs/SONDAGEM_PILHA_RS_0_41_3.md).

## RS 0.41.2 — Prólogos nativos e metadados de exceções Windows

O gerador PE32+ emite agora seções reais `.pdata` e `.xdata` com
intervalos `RUNTIME_FUNCTION` e informações `UNWIND_INFO` para a entrada
principal e funções com quadros fixos elegíveis. As descrições verificam
os bytes do prólogo, os salvamentos de `RBP`/`RBX` e a reserva de pilha.

```text
python compilar.py exemplos/funcoes.rts --alvo windows -O 8
```

**Cobertura parcial:** quadros com sondagem por várias páginas, rotinas
auxiliares e alguns usos de registradores ainda precisam de auditoria.
Esses trechos não recebem descrições fictícias. A opção
`HIGH_ENTROPY_VA` permanece desligada; `DYNAMIC_BASE` e
`NX_COMPAT` continuam ativos. A RS ainda não oferece proteção
completa de exceções nem garantia de conformidade ABI em todo o código.

[Detalhes técnicos, testes e restrições](docs/DESENROLAMENTO_WINDOWS_RS_0_41_2.md).

## RS 0.41.1 — Isolamento de dados ELF e diagnóstico Windows

No Linux, as mensagens constantes passaram a ocupar uma região
`PT_LOAD` com leitura permitida e **execução proibida**, separada do
código `r-xp`. Testes verificam as permissões reais em
`/proc/<pid>/maps` e executam programas de `-O 0` a `-O 8`.

No Windows, `DYNAMIC_BASE` e `NX_COMPAT` continuam ativos. A investigação
da alta entropia localizou uma escrita por ponteiro inválido durante
uma chamada do sistema para fechar arquivo. Ainda não identificamos
a origem exata da incompatibilidade; `HIGH_ENTROPY_VA` permanece
**desligado**. Também não fingimos suporte a `.pdata`/`.xdata`
sem metadados de desenrolamento corretos.

[Relatório, limites e critérios de segurança](docs/MEMORIA_EXECUTAVEIS_RS_0_41_1.md).

## RS 0.41 — Proteção do carregamento ELF e PE

A RS 0.41 melhora a segurança dos executáveis **sem exigir ferramentas
externas de compilação nem ambientes de execução adicionais**.

No **Linux**, os programas usam ELF64 `ET_DYN` (PIE), de modo que o núcleo
pode variar a base de carregamento, e o cabeçalho `PT_GNU_STACK` solicita
pilha não executável.

No **Windows**, a imagem PE32+ possui uma seção `.reloc` com realocação
`DIR64` efetivamente usada pela entrada do programa, e habilita
`DYNAMIC_BASE` (ASLR) e `NX_COMPAT`. A opção `HIGH_ENTROPY_VA`
continua **desligada**, pois provocou violações de acesso em certos
programas; não afirmamos suporte a alta entropia antes da correção
do gerador nativo.

As verificações comparam cabeçalhos, permissões, realocação e execução
real em Windows e Linux, de `-O 0` a `-O 8`. As assinaturas SHA-256
anteriores continuam arquivadas; novos arquivos de referência registram
o formato 0.41.

A RS ainda **não** oferece proteção integral da pilha, CFG, metadados
completos de desenrolamento de exceções no PE ou garantia de memória
segura. Não deve ser usada em produção.

[Especificação e limitações da RS 0.41](docs/SEGURANCA_EXECUTAVEIS_RS_0_41.md).

## RS 0.40D — Modelo comum de efeitos e propriedade

As análises de IR e da árvore sintática completa compartilham agora
um mesmo contrato de efeitos: leituras, escritas, E/S, possibilidade
de falha, arquivos, fluxo de controle e transições de propriedade.

```text
python compilar.py exemplos/aplicacoes/publicar_banco_rs039.rts --alvo linux -O 8 --mostrar-efeitos-do-programa
```

A opção `--salvar-efeitos-do-programa` também exporta JSON com
diagnósticos dos comandos modernos, mesmo quando a IR não os representa.
Chamadas e instruções desconhecidas são tratadas como potenciais
barreiras. **Nenhuma transformação nova foi habilitada no otimizador.**

[Contrato e limitações RS 0.40D](docs/CONTRATO_EFEITOS_RS_0_40D.md).

## RS 0.40C — Contrato verificável da representação intermediária

O compilador possui agora um diagnóstico para mostrar quais instruções e
expressões são representadas na IR, além dos motivos exatos para
selecionar o gerador conservador. Novos comandos não podem entrar
silenciosamente na IR antiga por meio da seleção de otimizações.

```text
python compilar.py exemplos/aplicacoes/analisar_entregas.rts --alvo linux -O 8 --mostrar-cobertura-intermediaria --mostrar-estrategia
```

A opção `--mostrar-cobertura-intermediaria` conta operações e explica
lacunas. Análises `--mostrar-ir`, `--mostrar-efeitos`, SSA e fluxo
não fingem suporte a um programa que só pode seguir pelo conservador;
o executável normal continua disponível. Os testes incluem casos
diferenciais entre `-O 0` e `-O 8` em Linux e Windows.

[Contrato, exemplos e limites da IR](docs/COBERTURA_INTERMEDIARIA_RS_0_40C.md).
Nenhuma dependência externa de execução foi adicionada.

## RS 0.40B — Proteção uniforme de abertura de arquivos

As APIs históricas e as mais recentes agora compartilham uma política
de abertura: no Linux, `O_NOFOLLOW|O_CLOEXEC`; no Windows,
`FILE_FLAG_OPEN_REPARSE_POINT` e verificação dos atributos do
identificador aberto **antes de escrever ou truncar**.
As regras de caminhos literais também foram centralizadas.
A proteção cobre o **nome final**, não os diretórios ancestrais;
os diretórios usados pela aplicação ainda devem ser confiáveis.

[Detalhes, limitações e testes](docs/POLITICA_CAMINHOS_RS_0_40B.md).

## RS 0.40A — Integridade da disposição de tipos

As dimensões de memória de valores compostos agora partem de uma única
regra no módulo `compilador/disposicao_tipos.py`. A análise semântica,
a emissão de código nativo e as listas dinâmicas consultam essa mesma
regra, inclusive para registros aninhados que contêm `bytes[N]`.
Os novos testes conferem crescimento e realocação em O0–O8,
nas duas plataformas.

A RS preserva a geração direta de executáveis independentes do
compilador. O compilador ainda é desenvolvido em Python e **ainda não é
autocompilado**. A política de usar português brasileiro sem acentos
nos identificadores novos e de manter independência de runtimes
externos obrigatórios está documentada em
[Princípios permanentes da RS](docs/PRINCIPIOS_RS.md).

## RS 0.39 — Publicação de arquivos e proteção de nomes

A RS 0.39 oferece novos recursos necessários à persistência segura:
`publique_arquivo("rascunho.rsd","banco.rsd",estado)` solicita uma
substituição de versão **após** o programa gravar, sincronizar e
fechar o arquivo provisório. No Linux usa `renameat` e sincroniza o
diretório; no Windows utiliza `MoveFileExA` com substituição e
`WRITE_THROUGH`, respeitando os limites de cada sistema.

`bloqueie_arquivo(arq,estado)` estabelece um bloqueio `flock`
não bloqueante no Linux (cooperativo), ou verifica a exclusão obtida
na abertura Windows (onde `CreateFileA` já usa compartilhamento
negado). `abra_arquivo` agora também aceita `texto[N]` como nome
dinâmico de arquivo, validado byte a byte: somente basename ASCII,
sem barras, travessias, caracteres de controle ou dispositivos
reservados no Windows.

Os testes incluem interrupções injetadas **antes e depois** da
publicação, verificando que nunca observamos a versão anterior
sobrescrita parcialmente nesses cenários. Isso **não** representa
prova de tolerância a queda de energia, nem implementa isolamento
ou transações do Dados RS.

Consulte a [especificação RS 0.39](docs/PUBLICACAO_ARQUIVOS_RS_0_39.md)
e o [programa de publicação real](exemplos/aplicacoes/publicar_banco_rs039.rts).

## RS 0.38 — recursos de arquivo com sincronização

Os novos comandos nativos permitem manter um arquivo aberto durante
várias operações e verificar a persistência solicitada ao sistema:

```text
inicio {
    seja arq: arquivo
    seja estado = 0
    seja dados: bytes[16]
    adicione_byte(dados, 82)
    abra_arquivo("arquivo.rsd", arq, "novo", estado)
    se estado != 0 {
        encerre(1)
    }
    grave_em(arq, dados, 0, estado)
    sincronize_arquivo(arq, estado)
    feche_arquivo(arq, estado)
}
```

Há criação exclusiva (`novo`), modos de leitura/alteração,
`grave_em`, `carregue_de`, `sincronize_arquivo` e
`feche_arquivo`, além de fechamento automático ao sair de escopos e
funções. Recursos `arquivo` não podem ser copiados. Falhas continuam
recuperáveis por códigos inteiros; a biblioteca
`importe "padrao/arquivos.rts"` fornece adaptação opcional a
`resultado[inteiro]`.

**Sincronizar não torna uma atualização atômica ou transacional.**
Consulte [o contrato RS 0.38](docs/ARQUIVOS_ABERTOS_RS_0_38.md)
e [a aplicação binária demonstrativa](exemplos/aplicacoes/persistencia_segura_rs038.rts).

## RS 0.37 — bytes seguros, persistência binária e saída de processo

A RS agora possui **`bytes[N]`**, um tipo de buffer binário separado
de `texto[N]`, com comprimento dinâmico e capacidade fixa verificada:

```text
inicio {
    seja dados: bytes[10]
    adicione_byte(dados, 82)
    adicione_byte(dados, 83)
    dados[1] = 255
    escreva(dados[1])
    escreva(tamanho(dados))
    encerre(0)
}
```

- `adicione_byte(destino, valor)`: anexa um inteiro na faixa 0 a 255,
  recusando ultrapassar a capacidade.
- `dados[indice]`: somente índices menores que `tamanho(dados)`
  podem ser lidos ou sobrescritos; sobrescrever não aumenta o tamanho.
- `limpe(dados)`: redefine o comprimento a zero (não apaga
  necessariamente todos os bytes da memória).
- `carregue_trecho` e `grave_trecho`: agora aceitam `bytes[N]` além
  dos buffers `texto[N]` legados; não convertem em UTF-8.
- `encerre(codigo)`: devolve ao sistema um código entre 0 e 255.
  Valores fora desse intervalo são rejeitados durante a execução.

O projeto continua experimental. A RS **não garante gravação atômica,
durabilidade após desligamento nem isolamento de transações**; também não
possui ainda drivers PostgreSQL, SQLite ou MariaDB.

Veja a [especificação RS 0.37](docs/BYTES_E_SAIDA_RS_0_37.md) e
[o exemplo de cabeçalho binário](exemplos/aplicacoes/criar_cabecalho_binario.rts).

## RS 0.36 — consolidação e aplicações de referência

A RS 0.36 **não introduz outro nível de otimização**. Ela consolida a escolha
entre o gerador conservador, a representação intermediária tipada e o
backend SSA. A escolha agora vem de uma mesma decisão no compilador e
na opção pública `--mostrar-estrategia`. Assim, um programa com
funções, registros, listas dinâmicas ou arquivos nativos não é apresentado
falsamente como otimizado via SSA só por ter sido compilado com `-O 8`.

```bash
python compilar.py exemplos/aplicacoes/analisar_entregas.rts --alvo linux -O 8 --mostrar-estrategia -o entregas
```

Há **duas aplicações executáveis escritas integralmente em RS**:

- [Copiador binário em blocos de 4096 bytes](exemplos/aplicacoes/copiar_arquivo_em_blocos.rts):
  lê `origem.bin` e cria `copia.bin`, preservando dados arbitrários,
  inclusive arquivos vazios; informa falhas recuperáveis de leitura/gravação.
  Por segurança, recusa um destino que já exista, pois a RS ainda não
  dispõe de truncamento atômico; nomes são literais por enquanto.
- [Analisador de 150 entregas](exemplos/aplicacoes/analisar_entregas.rts):
  utiliza listas dinâmicas tipadas, registros, empréstimos e funções para
  calcular quantidade e receita em centavos. **Este programa é apenas
  em memória**; persistência estruturada será uma etapa posterior.

[Documentação da RS 0.36 e matriz O0–O8](docs/CONSOLIDACAO_RS_0_36.md).
Os testes executam os binários nativos, com resultados e arquivos
conferidos independentemente, e não apenas comparam fontes ou ASTs.

## RS 0.35 — acesso binário posicional

Dois comandos permitem modificar partes de arquivos sem truncar o conteúdo
e recuperar resultados de I/O sem encerrar o programa:

```text
inicio {
    seja pagina: texto[100]
    seja estado = 0
    copie(pagina, "Entrega 101")
    grave_trecho("banco.rsd", pagina, 4096, estado)
    carregue_trecho("banco.rsd", pagina, 4096, 11, estado)
    escreva(estado)
}
```

`estado` recebe a quantidade de bytes processados (`0` inclusive no EOF)
ou códigos negativos para falha de abertura, operação, parâmetros e
fechamento. Os dados são bytes arbitrários, embora o armazenamento inicial
ainda seja `texto[N]`. A gravação não é atômica nem durável após quedas de
energia; sincronização e transações permanecem pendentes.

Veja [a especificação das operações](docs/ARQUIVOS_POSICIONAIS_RS_0_35.md)
e [o exemplo executável](exemplos/arquivos_posicionais.rts).

## RS 0.34 — persistência nativa de arquivos (experimental)

Dois comandos permitem salvar e carregar os bytes de um buffer `texto[N]`
sem depender de Python na execução:

```text
inicio {
    seja registro: texto[100]
    copie(registro, "entrega 101, concluida")
    grave_arquivo("entregas.txt", registro)

    limpe(registro)
    carregue_arquivo("entregas.txt", registro)
    escreva(registro)
}
```

`grave_arquivo` cria ou substitui o arquivo, gravando exatamente o comprimento
atual do texto, sem acrescentar quebra de linha. `carregue_arquivo` lê todo o
arquivo, substituindo os bytes e o comprimento do buffer; se o arquivo for
maior do que a capacidade, encerra o programa com erro, sem cortar dados
silenciosamente. Falhas de abertura, leitura, gravação e fechamento também
geram erro. Nomes de arquivo são literais relativos, ASCII e sem segmentos
`..`, por enquanto; os diretórios intermediários precisam existir.

Esses recursos operam sobre conteúdo em bytes (não serializam registros).
Veja [o guia da RS 0.34](docs/ARQUIVOS_RS_0_34.md) e
[o exemplo de persistência](exemplos/persistencia_texto.rts).

## RS 0.33 — transferência de propriedade e duração por escopo

A RS agora implementa `mova(destino, origem)` para `lista[]`. A operação
libera o antigo destino, transfere o armazenamento da origem **sem copiar
elementos** e invalida a origem. Usá-la novamente sem outra transferência
causa um erro controlado.

Listas dinâmicas podem ser declaradas em blocos `se`, `enquanto` e
`para`. A saída normal, `pare` e `continue` liberam as listas locais;
`retorne` libera os descritores ativos da função, mesmo que existam
declarações não alcançadas.

```text
inicio {
    seja principal: lista[]
    para i de 1 ate 4 {
        seja temporaria: lista[]
        adicione(temporaria, i * 10)
        se i == 4 {
            mova(principal, temporaria)
        }
    }
    escreva(principal[0])
}
```

**Saída esperada:** `40`.

### Empréstimo explícito e temporário, somente para leitura

Funções podem receber `emprestimo[lista]` usando `empreste(lista)`, sem
copiar os elementos nem adquirir a propriedade. Na função, são permitidas
consultas por índice, `tamanho` e `capacidade`. O empréstimo pode ser
repassado a outra função, mas nunca retornado, guardado em outra variável,
reatribuído ou utilizado para alterar/liberar a lista.

```text
funcao total(valores: emprestimo[lista]) -> inteiro {
    seja soma = 0
    para i de 0 ate tamanho(valores) - 1 {
        soma = soma + valores[i]
    }
    retorne soma
}
inicio {
    seja vendas: lista[]
    adicione(vendas, 12)
    adicione(vendas, 18)
    escreva(total(empreste(vendas)))
    escreva(vendas[0])
}
```

**Saída esperada:** `30` e `12`. O compilador impede a saída de referências
emprestadas do contexto da chamada; a validade da lista original também é
verificada em tempo de execução.

Listas dinâmicas agora aceitam `lista[inteiro]` e `lista[logico]`
(além do legado `lista[]` como inteiro). O empréstimo preserva o tipo:
`emprestimo[lista[logico]]`, por exemplo. Transferências entre listas
de tipos diferentes são erros de compilação. Registros declarados com `tipo` também podem ser elementos de
`lista[Registro]`. O armazenamento cresce com a largura real do registro,
inclusive campos aninhados, e permite `adicione(lista, registro)`,
`lista[indice] = registro`, cópias por valor com
`seja copia: Registro = lista[indice]` e empréstimos somente para leitura.
Um índice não cria uma referência prolongada ao elemento; a leitura
de um registro produz uma cópia independente. Ainda não é possível
editar campos diretamente como `lista[indice].campo`. Textos dinâmicos
e tipos arbitrários compostos permanecem em planejamento.
A RS permanece experimental. Leia
[`docs/PROPRIEDADE_E_ESCOPOS_RS_0_33.md`](docs/PROPRIEDADE_E_ESCOPOS_RS_0_33.md)
e o [guia de listas tipadas](docs/LISTAS_TIPADAS_RS_0_33.md), com o
[exemplo de entregas](exemplos/entregas_tipadas.rts).

## Histórico: RS 0.32 — listas dinâmicas e propriedade exclusiva

A linguagem agora reconhece **lista[]**, com armazenamento nativo que cresce conforme os dados são adicionados e é liberado automaticamente no fim da função ou do programa proprietário.

```text
inicio {
    seja pedidos: lista[]
    adicione(pedidos, 10)
    adicione(pedidos, 20)

    escreva(tamanho(pedidos))
    escreva(pedidos[1])

    remova_ultimo(pedidos)
    escreva(tamanho(pedidos))
}
```

**Saída:** 2, 20 e 1, cada um em uma linha.

As operações incluem `adicione`, `remova_ultimo`, `limpe_lista`, `libere`, `tamanho`, `capacidade` e índices verificados para leitura e escrita. O gerador usa `mmap/munmap` no Linux e `VirtualAlloc/VirtualFree` no Windows. A lista inicia com zero posições e cresce conforme necessário, sem um tamanho fixo declarado no código RS.

**Propriedade única:** nesta etapa, cada lista dinâmica pertence a um único escopo de função ou `inicio`. Não é possível copiá-la, passá-la como argumento, retorná-la ou armazená-la em registros. Declarações em condicionais ou laços também continuam restritas enquanto o gerenciamento completo de pontos de saída estiver em construção. Isso evita referências pendentes e liberações duplicadas. A liberação explícita torna a lista inutilizável, com erro controlado em acessos posteriores; listas sem liberação explícita são liberadas ao final do proprietário.

**Exemplo:** [`exemplos/listas_dinamicas.rts`](exemplos/listas_dinamicas.rts). Veja as [regras completas de propriedade, segurança e limitações](docs/LISTAS_DINAMICAS_RS_0_32.md). As listas fixas `lista[N]`, os resultados tipados e os níveis de otimização de `-O 0` a `-O 8` continuam disponíveis. Nenhum novo nível de otimização foi criado.

## Histórico: RS 0.31 — resultados genéricos e propagação de falhas

O sistema de tipos agora aceita **resultado[T]**, especializado na compilação para
cada tipo concreto utilizado, inclusive **inteiros, lógicos, registros, textos e listas fixas**.

```text
funcao dividir(a: inteiro, b: inteiro) -> resultado[inteiro] {
    se b == 0 {
        retorne falha[inteiro](1)
    }
    retorne sucesso[inteiro](a / b)
}

funcao calcular(n: inteiro) -> resultado[inteiro] {
    seja parte = dividir(n, 2)
    propague parte
    retorne sucesso[inteiro](parte.valor + 5)
}

inicio {
    seja resposta = calcular(20)
    escreva(resposta.valido)
    escreva(resposta.valor)
}
```

**Resultado:** 1 e 15, um por linha.

- **resultado[T]** possui campos `valido`, `valor` e `codigo_erro`.
- **sucesso[T](valor)** constrói um resultado válido.
- **falha[T](codigo)** constrói um resultado inválido, com valor inicializado.
- **propague nome** encaminha o erro de uma variável de resultado para a função atual quando `valido` é falso. Funciona apenas em funções com retorno `resultado[T]` e exige nome de variável explícito.
- Tipos compostos e capacidades são conferidos estaticamente. **resultado[inteiro] e resultado[logico] são tipos diferentes**; não há conversão implícita.
- Os registros da Biblioteca Padrão RS 0.30 continuam disponíveis e não são automaticamente convertidos para os novos resultados genéricos.

**Escopo real:** o recurso é uma *especialização estática*, não uma implementação de funções genéricas arbitrárias ou exceções. Transbordamentos nativos e falhas de índices continuam encerrando a execução conforme a proteção anterior — `propague` não os captura.

**Exemplo novo:** [`exemplos/resultados_genericos.rts`](exemplos/resultados_genericos.rts). Veja a [documentação completa e limitações](docs/RESULTADOS_GENERICOS_RS_0_31.md). Nenhum nível de otimização foi acrescentado.

## Histórico: RS 0.30 — resultados tipados e erros explícitos

A Biblioteca Padrão agora fornece dois **tipos de resultado**: `ResultadoInteiro` e `ResultadoLogico`. Cada um possui `valido`, `valor` e `codigo_erro`. São registros realmente implementados em `.rts`; a linguagem verifica os tipos na compilação e copia os resultados por valor, sem depender de Python na execução.

```text
importe "padrao/resultados.rts" como resultados
importe "padrao/matematica_segura.rts" como segura

inicio {
    seja divisao: resultados.ResultadoInteiro = segura.dividir(10, 0)

    se divisao.valido {
        escreva(divisao.valor)
    } senao {
        escreva("Falha de divisao detectada")
        escreva(divisao.codigo_erro)
    }

    seja raiz: resultados.ResultadoInteiro = segura.raiz_quadrada_inteira(81)
    escreva(resultados.inteiro_ou(raiz, -1))
}
```

**Saída:** `Falha de divisao detectada`, `1` e `9`, em linhas separadas.

O módulo `padrao/resultados.rts` contém os construtores de sucesso e falha, dois tipos de resultado, funções de consulta com valor alternativo e os códigos padronizados. `padrao/matematica_segura.rts` disponibiliza **dez operações com verificação explícita de domínio**: `dividir`, `resto`, `fatorial`, `fibonacci`, `mdc`, `mmc`, `potencia_natural`, `raiz_quadrada_inteira`, `eh_primo` e `limitar`.

**Limitação importante:** são registros tipados da Biblioteca Padrão, **não** um tipo genérico embutido `resultado[T]`. Erros de domínio conhecidos são devolvidos como valores; **transbordamentos em multiplicações gerais ainda podem encerrar o executável**. As funções antigas com retornos convencionais continuam disponíveis para não quebrar programas anteriores. A RS 0.30 não introduziu um novo nível de otimização.

**Exemplo completo:** [`exemplos/resultados_tipados.rts`](exemplos/resultados_tipados.rts). Consulte a [documentação de resultados e códigos de erro](docs/RESULTADOS_TIPADOS_RS_0_30.md).

## Histórico: RS 0.29 — Biblioteca Padrão escrita em RoteiroSimples

A primeira Biblioteca Padrão oficial está em **`biblioteca_padrao/`**, com **30 funções reais** implementadas em arquivos `.rts`, organizadas em quatro módulos: `numeros` (9), `matematica` (8), `estatistica` (6) e `listas` (7).

```text
importe "padrao/numeros.rts" como numeros
importe "padrao/matematica.rts" como matematica
importe "padrao/estatistica.rts" como estatistica
importe "padrao/listas.rts" como listas

inicio {
    seja valores: lista[5]
    valores[0] = 8
    valores[1] = 3
    valores[2] = 8
    valores[3] = -2
    valores[4] = 5

    escreva(numeros.absoluto(-25))
    escreva(matematica.fatorial(5))
    escreva(estatistica.media_cinco(valores))
    seja ordenados: lista[5] = listas.ordenar_cinco(valores)
    escreva(ordenados[0])
}
```

**Resultado:** `25`, `120`, `4` e `-2`, cada um em uma linha.

`padrao/` é um prefixo especial: o compilador localiza sua biblioteca instalada, mesmo quando o programa do usuário está em outra pasta. Os módulos são resolvidos na compilação, incorporados ao executável nativo e não precisam existir ao lado do programa executável. Importações próprias ainda são relativas ao projeto e mantêm a proteção contra fuga de diretórios.

**Escopo honesto:** estatística e listas trabalham, por ora, com `lista[5]`; não temos listas dinâmicas ou tipos genéricos. Os resultados são inteiros de 64 bits, com verificações de transbordamento. `fatorial` só atende 0 a 20 e devolve `-1` fora dessa faixa; expoente negativo de `potencia_natural` devolve `0`, como convenção provisória. Essas regras e as demais pré-condições estão no [manual completo da Biblioteca Padrão](docs/BIBLIOTECA_PADRAO_RS_0_29.md).

**Exemplo executável:** [`exemplos/biblioteca_padrao.rts`](exemplos/biblioteca_padrao.rts). Os níveis existentes de `-O 0` a `-O 8` foram mantidos, sem criar outro. A Biblioteca Padrão é escrita na linguagem RS; o Python continua necessário apenas para executar o compilador de desenvolvimento.

## Histórico: RS 0.28 — espaços de nomes e visibilidade

Podemos usar funções e tipos com nomes iguais em módulos diferentes, graças à importação com apelido:

```text
// principal.rts
importe "financeiro.rts" como financeiro
importe "estoque.rts" como estoque

inicio {
    seja pedido: financeiro.Pedido
    pedido.valor = 25
    escreva(financeiro.calcular(pedido))
}
```

No módulo `financeiro.rts`, utilizamos `publico funcao calcular(...)` para permitir a chamada pelo importador e `privado funcao acrescentar_taxa(...)` para proteger uma função de uso interno. Isso também funciona com declarações de `tipo`.

- **`publico`** deixa a definição acessível para quem importar o módulo.
- **`privado`** impede o acesso externo, sem impedir chamadas dentro do próprio módulo.
- Declarações sem modificador permanecem públicas para preservar os programas anteriores.
- **`importe "arquivo.rts" como apelido`** exige nomes qualificados (`apelido.funcao`, `apelido.Tipo`); a forma anterior sem apelido continua funcionando.
- Módulos importados duas vezes não são duplicados; nomes e tipos internos de arquivos distintos permanecem separados.
- Erros de conflito, acesso privado, nome inexistente e dependência circular são diagnosticados na compilação.

**Exemplo executável:** [`exemplos/espacos_nomes/principal.rts`](exemplos/espacos_nomes/principal.rts), com dois tipos `Pedido` e duas funções `calcular`. Saída: `RS 0.28: espacos de nomes`, `30` e `50`.

Consulte a [especificação dos espaços de nomes](docs/ESPACOS_DE_NOMES_RS_0_28.md). Mantivemos os níveis de `-O 0` a `-O 8`; não criamos outro nível de otimização.

## Histórico: RS 0.27 — sistema de módulos em português

Agora podemos organizar um projeto em **vários arquivos `.rts`**, reutilizando tipos e funções próprias com o comando `importe`:

```text
// exemplos/modulos/valores.rts
funcao acrescentar_taxa(valor: inteiro) -> inteiro {
    retorne valor + 5
}
```

```text
// exemplos/modulos/pedidos.rts
importe "valores.rts"
tipo Pedido {
    preco: inteiro
    quantidade: inteiro
}
funcao calcular_pedido(pedido: Pedido) -> inteiro {
    retorne acrescentar_taxa(pedido.preco * pedido.quantidade)
}
```

```text
// exemplos/projeto_modulos.rts
importe "modulos/pedidos.rts"
inicio {
    seja pedido: Pedido
    pedido.preco = 25
    pedido.quantidade = 4
    escreva(calcular_pedido(pedido))
}
```

**Resultado:** `105`. O compilador resolve as dependências, reúne os arquivos e gera um único executável Windows ou Linux, sem carregar módulos durante a execução.

A importação usa caminho relativo ao arquivo que importa; apenas arquivos `.rts` dentro da pasta do projeto são aceitos. Importações repetidas são reunidas uma única vez, dependências circulares e nomes duplicados geram erros. Na RS 0.27 todos os tipos e funções compartilhavam o mesmo espaço global. A RS 0.28 adicionou apelidos, qualificadores e elementos privados.

**Exemplo:** [`exemplos/projeto_modulos.rts`](exemplos/projeto_modulos.rts). Veja [a documentação completa dos módulos](docs/MODULOS_RS_0_27.md). O parâmetro `--mostrar-modulos` mostra os arquivos carregados. Os níveis de otimização continuam de `-O 0` a `-O 8`, sem acrescentar outro nível.

## Histórico: RS 0.26 — registros aninhados e chamadas compostas diretas

Registros podem conter outros registros, listas de inteiros e buffers UTF-8 de capacidade declarada. Os campos são acessados por caminhos completos e verificados na compilação.

```text
tipo Endereco {
    numero: inteiro
    rua: texto[24]
}
tipo Cliente {
    endereco: Endereco
    notas: lista[3]
}
funcao criar_cliente(numero: inteiro) -> Cliente {
    seja cliente: Cliente
    cliente.endereco.numero = numero
    copie(cliente.endereco.rua, "Rua Mineira")
    cliente.notas[0] = 12
    cliente.notas[1] = 18
    retorne cliente
}
funcao calcular(cliente: Cliente) -> inteiro {
    retorne cliente.endereco.numero + cliente.notas[0] + cliente.notas[1]
}
inicio {
    escreva(calcular(criar_cliente(70)))
}
```

**Saída:** `100`.

Além dos registros aninhados, agora é possível passar diretamente o resultado composto de uma função como argumento de outra, como `calcular(criar_cliente(70))`. O compilador cria uma região temporária local para o resultado intermediário e preserva a avaliação da esquerda para a direita. Cópias de registros, listas e textos permanecem **por valor**, sem compartilhamento implícito de memória. Tamanhos e capacidades continuam fazendo parte dos tipos.

Registros são declarados em ordem: quando um campo utiliza um tipo próprio, esse tipo deve ter sido declarado anteriormente. Não há tipos recursivos por valor (que teriam tamanho infinito), memória dinâmica ou referências emprestadas nesta versão. Não criamos novos níveis de otimização.

**Exemplo:** [`exemplos/registros_aninhados.rts`](exemplos/registros_aninhados.rts). Detalhes em [`docs/REGISTROS_ANINHADOS_RS_0_26.md`](docs/REGISTROS_ANINHADOS_RS_0_26.md).

## Histórico: RS 0.25 — dados compostos em funções

A linguagem agora permite passar e devolver **registros, listas de inteiros e buffers UTF-8 por valor**, com cópias independentes entre o chamador e a função.

```text
tipo Produto {
    preco: inteiro
    quantidade: inteiro
}
funcao novo_produto(valor: inteiro) -> Produto {
    seja p: Produto
    p.preco = valor
    p.quantidade = 4
    retorne p
}
funcao quadrados() -> lista[3] {
    seja numeros: lista[3]
    numeros[0] = 1
    numeros[1] = 4
    numeros[2] = 9
    retorne numeros
}
inicio {
    seja p: Produto = novo_produto(25)
    seja valores: lista[3] = quadrados()
    escreva(p.preco * p.quantidade)
    escreva(valores[2])
}
```

**Resultado:** `100` e `9`, cada um em uma linha.

O tamanho da lista e a capacidade do buffer fazem parte do tipo: `texto[16]` não é intercambiável com `texto[32]`. As funções podem usar `copie`, `junte` e `limpe` em seus buffers locais e parâmetros; a leitura `leia` dentro de funções permanece indisponível. O resultado de função que devolve um valor composto precisa de destino explícito; armazene-o em variável antes de passá-lo a outra função. Na RS 0.25, registros aninhados e passagem direta de resultados compostos como argumentos ainda não estavam disponíveis; ambos foram introduzidos na RS 0.26. Listas dinâmicas permanecem pendentes.

**Exemplo executável:** [`exemplos/funcoes_compostas.rts`](exemplos/funcoes_compostas.rts). Veja a [especificação da RS 0.25](docs/FUNCOES_COMPOSTAS_RS_0_25.md). Mantivemos os níveis históricos de `-O 0` a `-O 8`; não adicionamos outro nível.

## Histórico: RS 0.24 — registros e recursão controlada

Esta atualização prioriza **fundamentos de linguagem**, não outro nível de otimização.
Agora o programador pode declarar um tipo composto por campos `inteiro` e `logico`,
criar registros, ler e alterar seus campos e enviá-los **por valor** a funções nativas.
Chamadas recursivas diretas e indiretas têm proteção contra esgotamento do orçamento
de pilha do trecho recursivo.

```text
tipo Pedido {
    preco: inteiro
    quantidade: inteiro
    ativo: logico
}

funcao calcular(pedido: Pedido) -> inteiro {
    se pedido.ativo {
        retorne pedido.preco * pedido.quantidade
    } senao {
        retorne 0
    }
}

funcao fatorial(n: inteiro) -> inteiro {
    se n <= 1 {
        retorne 1
    } senao {
        retorne n * fatorial(n - 1)
    }
}

inicio {
    seja pedido: Pedido
    pedido.preco = 25
    pedido.quantidade = 4
    pedido.ativo = verdadeiro
    escreva(calcular(pedido))
    escreva(fatorial(5))
}
```

**Saída esperada:** `100` e `120`, um em cada linha. Arquivo completo:
[`exemplos/registros_recursao.rts`](exemplos/registros_recursao.rts).

### Regras dos registros e funções

- `tipo Nome { ... }`: os campos têm nome próprio e tipo `inteiro` ou `logico`.
  Cada campo usa um espaço de 8 bytes; definições de tipos antecedem funções e `inicio`.
- `seja registro: Nome`: cria um registro local, com os campos zerados.
  O acesso `registro.campo` verifica nome e tipo na compilação.
- Um parâmetro `pedido: Pedido` recebe **cópia independente** dos campos.
  Uma alteração dentro da função não altera o valor do chamador.
- Funções podem chamar outras funções e chamar a si mesmas. Argumentos e
  retornos são tipados; os retornos ainda aceitam somente `inteiro` ou `logico`.
- Na RS 0.24, na parte recursiva da execução, o compilador controlava um orçamento acumulado
  de pilha de **1 MiB** e encerra com diagnóstico e código 1 quando ele é excedido,
  antes de reservar o quadro recursivo seguinte. A sondagem de páginas para grandes
  quadros locais continua disponível. Esse limite de segurança não é um máximo
  geral de variáveis, listas, buffers ou tamanho de executável.
  Desde a RS 0.42A.1, o orçamento de 768 KiB inclui o principal, todos os
  quadros, argumentos e temporários, com verificação em todas as chamadas.
- Nesta versão o gerador de código conservador executa funções e registros; as
  análises avançadas de atribuição única e otimização de memória ainda não são
  aplicadas a programas que usam esses novos recursos.

### Limitações históricas da RS 0.24 (superadas parcialmente nas versões seguintes)

Na RS 0.24 ainda não havia retorno de registros inteiros nem passagem de listas e buffers às funções. Esses recursos chegaram na RS 0.25; registros aninhados e campos compostos, na RS 0.26. Ainda não há empréstimos de referências,
alocação dinâmica, ponteiros brutos ou funções que recebam textos. O controle de pilha
não substitui um sistema completo de segurança de memória nem uma auditoria do código
nativo. Não se promete segurança para aplicações de produção.

## Começar no Windows

1. Instale Python 3.10 ou posterior e confirme `py -3 --version`.
2. Baixe ou clone este repositório e extraia o pacote em uma pasta.
3. Execute **`INICIAR_RS.bat`** e escolha **1** para compilar e executar a demonstração
   das listas dinâmicas da RS 0.32. A opção **2** abre o mesmo exemplo no Bloco de Notas.
4. Para executar os testes, escolha **3**.

Via PowerShell:

```powershell
py -3 compilar.py exemplos\listas_dinamicas.rts --alvo windows -O 8 -o roteiro_windows.exe
.\roteiro_windows.exe
py -3 -m unittest discover -s testes -v
```

## Compilar no Linux

Requer sistema Linux e processador x86-64:

```bash
python3 compilar.py exemplos/listas_dinamicas.rts --alvo linux -O 8 -o roteiro_linux
./roteiro_linux
python3 -m unittest discover -s testes -v
```

O compilador aceita os níveis históricos **`-O 0` até `-O 8`**. Na 0.42N,
programas escalares com funções elegíveis usam IR com transformações até O3
e emissão SSA com alocação em O4–O8;
registros, donos, empréstimos e arquivos continuam no gerador conservador.
`--mostrar-estrategia` informa o caminho e o nível efetivos.

## Recursos presentes na RS 0.42N

| Recurso | Situação |
|---|---|
| Inteiros de 64 bits, lógicos, expressões e erros aritméticos | Implementado |
| `escreva`, `leia`, condições, `enquanto`, `para`, `pare` e `continue` | Implementado |
| Escopos léxicos e ocultação de nomes locais | Implementado desde 0.23 |
| Funções, parâmetros e retornos numéricos e lógicos | Implementado desde 0.23 |
| Funções escalares na IR, dobramento e propagação de constantes | Implementado na 0.42J; propagação SSA entre blocos na 0.42L |
| CFG/fluxo por função escalar, parâmetros de entrada, retornos e efeitos transitivos | Implementado na 0.42K |
| SSA e alocação nativa por função escalar, com chamadas e recursão | Implementado na 0.42L em O4–O8 |
| Campanha gerada com oráculo independente, reprodução e redução de falhas | Implementado na 0.42J; corpus estruturado limitado |
| Cobertura Python de linhas/ramos e matriz CI Python 3.10/3.11/3.14 | Implementado na 0.42J |
| Medição O0–O8 com gerador, hashes e tempos individuais | Implementado na 0.42J; execuções intercaladas na 0.42K |
| Tipos compostos com campos escalares e passagem por valor | Implementado desde 0.24 |
| Recursão direta e indireta com orçamento de pilha | Implementado desde 0.24 |
| Listas fixas com índices verificados e buffers de texto UTF-8 | Implementado |
| Memória dimensionada para quadros locais, sondagem de páginas | Implementado |
| Representação intermediária tipada, fluxo de controle, versões únicas, memória versionada | Implementado para a parte já suportada da linguagem |
| Registros aninhados, campos de listas e texto | Implementado na 0.26 |
| Importação de módulos e resolução de dependências | Implementado na 0.27 |
| Espaços de nomes com apelidos e visibilidade pública/privada | Implementado na 0.28 |
| Biblioteca Padrão RS escrita em .rts, incluindo listas e resultados tipados | Implementado desde 0.29; ampliado nas revisões seguintes |
| Resultados tipados e operações matemáticas com erro explícito | Implementado na 0.30 |
| resultado[T], sucesso[T], falha[T] e propague | Implementado na 0.31 |
| `lista[]` e proprietário exclusivo com liberação automática | Implementado na 0.32 |
| Transferência `mova`, limpeza por escopo, empréstimo imutável | Implementado na 0.33 |
| Parâmetros/retornos de listas proprietárias e `mova(origem)` em expressão | Primeiro marco experimental na 0.42A.1 |
| Texto UTF-8 dinâmico, funções proprietárias e empréstimos de leitura | Implementado na 0.42A.2 |
| Contagem Unicode, igualdade de conteúdo e consulta explícita de bytes | Implementado na 0.42A.2 |
| Conversão explícita UTF-8 entre texto e bytes, com erro recuperável | Implementado na 0.42M |
| Cadastro variável em RS, serialização versionada e persistência por snapshot | Prova experimental na 0.42M; sem transações ou recuperação automática |
| Retomada de cadastro com duas cópias, confirmação, geração e trava estável | Prova experimental na 0.42N; processos cooperantes, sem ACID ou garantia absoluta após perda de energia |
| `consulte_arquivo` com ausência distinta de falha e recusa de links finais | Implementado na 0.42N; nome literal ASCII simples no diretório corrente |
| Bytes dinâmicos, funções proprietárias e empréstimos de leitura | Implementado na 0.42A.3 |
| Biblioteca de análise léxica escrita em RS | Implementado na 0.42C |
| `e`, `ou` e `nao` com operandos lógicos, precedência e curto-circuito | Implementado na 0.42O; palavras reservadas e classe léxica 6 em RS |
| Codificação binária em RS e prova `.rsd` com 100 registros | Implementado; ainda não é um motor de banco |
| Campos dinâmicos em registros aninhados e movimento do agregado | Implementado na 0.42D/0.42E |
| Parâmetros e retornos de registros proprietários | Implementado na 0.42F |
| Resultados com texto, bytes e registros proprietários | Implementado na 0.42G |
| Biblioteca de validação e composição de documentos em RS | Implementado na 0.42G |
| Coleções de registros proprietários, retirada e descarte por elemento | Implementado na 0.42H |
| Listas de registros em campos e coleções proprietárias aninhadas | Implementado na 0.42H; até 32 níveis |
| Empréstimos de registros e elementos de coleções para leitura dos campos | Implementado na 0.42I; duração da chamada |
| Busca por título e totalização de conteúdo na biblioteca de documentos em RS | Implementado na 0.42I |
| Consultas gerais e seleção de listas em RS | Acrescentadas na 0.42A.1 |
| ABI e desenrolamento Windows com ensaios reais | Consolidado na 0.41.5; regressões mantidas |
| Contrato comum de disposição, efeitos e propriedade | Consolidado nas revisões 0.40 e neste marco |
| Listas dinâmicas tipadas para inteiros, lógicos e registros | Implementado na 0.33 |
| Leitura e gravação de arquivos inteiros | Implementado na 0.34 |
| Leitura e gravação binária por posição, com estado de erro recuperável | Implementado na 0.35 |
| Tipo `bytes[N]`, limites binários e `encerre(codigo)` | Implementado na 0.37 |
| Recursos `arquivo`, leitura/escrita posicional, sincronização e fechamento automático | Implementado na 0.38 |
| Publicação por renomeação, bloqueio não bloqueante e basename variável verificado | Implementado na 0.39 |
| Passagem direta de resultados compostos a outras funções | Implementado na 0.26 |
| IR/CFG/SSA de registros, donos, empréstimos e arquivos | Ainda não |
| Resultados aninhados/de listas dinâmicas, empréstimos mutáveis, reais/decimais e FFI | Ainda não |

## Organização atual

- `compilador/`: léxico, análise sintática, escopos, tipos, representação intermediária
  e análises de fluxo.
- `backend/`: emissão direta de instruções x86-64 e geração de PE/ELF.
- `biblioteca_padrao/`: funções oficiais em módulos `.rts`, incluindo números, matemática, estatística, listas e resultados tipados.
- `compilador/propriedade.py`: contrato de cópia, transferência, empréstimo e descarte dos valores.
- `backend/valores_dinamicos.py`: operações comuns dos descritores proprietários.
- `backend/memoria_dinamica.py`: reserva, realocação, movimentação e liberação compartilhadas.
- `backend/textos_dinamicos.py`: vistas UTF-8, validação, leitura e operações sobre texto crescente.
- `backend/listas_dinamicas.py`: gerador de alocação e liberação nativas das listas de propriedade exclusiva.
- `bibliotecas/`: compatibilidade com antigas operações matemáticas internas.
- `exemplos/`: programas `.rts`, inclusive a demonstração nova.
- `testes/`: verificações estáticas, execução dos executáveis e regressões.
- `docs/`: notas da arquitetura e [histórico do README até a RS 0.23](docs/HISTORICO_README_ATE_RS_0_23.md).
- `sintaxe.py`, `codigo_nativo.py` e `ir.py`: interfaces antigas conservadas por compatibilidade.

## Próximas prioridades

**Consolidar persistência e memória:** a 0.42N acrescenta retomada com duas
cópias e atualização condicional por geração sob trava, sobre o cadastro
variável da 0.42M. As próximas etapas devem definir orçamento de memória,
sincronização do diretório na criação, migração e ensaios de falhas do sistema
e perda de energia antes de ampliar as garantias. RSCV e RSCN são formatos
experimentais, disponíveis em arquivos separados sem migração automática;
a prova anterior de 100 registros continua disponível. Transações, WAL e
índices seguem pendentes. O Dados RS será um projeto próprio, separado do
compilador.

Recursos proprietários precisam de contratos de memória na IR antes de
receber as transformações SSA já aplicadas às funções escalares. Oráculos,
campanhas e medições permanecem como referência. O léxico em RS permite
avançar gradualmente a análise sintática rumo à autocompilação.
A 0.42O acrescenta os operadores lógicos em português. Tipos reais/decimais,
expansão dos desvios internos dessas expressões no CFG e uma análise sintática
escrita em RS continuam no roteiro.
O motor e suas bibliotecas devem aproveitar estas bases; o Studio depende
de diagnósticos e serviços reutilizáveis e de uma futura interface nativa.

O projeto ainda é experimental, não pronto para produção. Não estamos acrescentando níveis de otimização.

Ainda não foi escolhida uma licença para publicação do código.
