# Estrategia de independencia progressiva — Ecossistema RS

## Principio

A RoteiroSimples (RS) deve permitir criar aplicativos, jogos e sistemas
profissionais em portugues brasileiro, com um nucleo proprio e
interoperabilidade explicita. A independencia e uma meta **verificavel**
por builds reproduziveis, e nao uma proibicao absoluta de bibliotecas
externas.

Uma biblioteca externa pode ser utilizada quando o projeto a declara,
sem obrigar os demais programas RS a carregar ou distribuir essa biblioteca.

## Trilhas de desenvolvimento e marcos de validacao

### 1. Nucleo, linguagem e bibliotecas fundamentais

Desenvolver com prioridade tipos, escopos e tempo de vida, erros recuperaveis,
manipulacao de memoria, operacoes matematicas, textos UTF-8, bytes,
colecoes, arquivos, busca e ordenacao. Implementar bibliotecas em RS
sempre que tecnicamente adequado, respeitando as interfaces do sistema
operacional quando for necessario.

**Marco de verificacao:** programas de referencia escritos em RS
compilados em Windows e Linux, com testes funcionais, memoria e falhas.

### 2. Autocompilacao e ferramentas minimas (inicia desde ja)

Continuar o compilador escrito em RS em paralelo as bibliotecas acima:
analise lexica, sintatica, semantica, representacao intermediaria, emissao
nativa e cadeia de bootstrap. Documentar as dependencias restantes do
compilador Python e reduzi-las por etapas.

Introduzir testes automaticos, mensagens de erro em PT-BR, um depurador
minimo e ferramentas basicas de construcao e distribuicao. Preparar
RS Studio inicialmente como editor/terminal e interface aos testes, sem
bloquear o progresso do compilador por uma IDE grafica completa.

**Marco de verificacao:** compilar o compilador com a versao anterior,
recompilar com o binario gerado, comparar resultados, executar suite de
regressao e repetir a construcao em ambiente limpo. A autocompilacao
nao deve ser anunciada como pronta antes dessa demonstracao.

### 3. Infraestrutura e Dados RS

Desenvolver rede, sockets e protocolos documentados, persistencia,
formatos interoperaveis, transacoes, indices e recuperacao no Dados RS.
Separar operacoes criptograficas e primitivas do sistema operacional de
componentes especificos de plataforma, sem inventar criptografia.

**Marco de verificacao:** aplicacao RS com cadastro persistente, consultas,
concorrencia, tratamento de falhas e recuperacao apos interrupcao.

### 4. Graficos, interacao e midia

Consolidar janelas/eventos nativos e componentes de interface; implementar
desenho 2D e audio por interfaces multiplataforma. Somente depois
priorizar motores 3D e renderizacao avancada, que exigem investimento
consideravel e nao devem bloquear o nucleo.

**Marco de verificacao:** uma aplicacao grafica escrita em RS, com
entrada, eventos, arquivos e testes de regressao em cada plataforma.

### 5. Interoperabilidade (permanente)

Manter chamadas a bibliotecas de sistema e externas explicitamente
declaradas, controle de ABI, versoes, permissoes de carregamento,
gerenciamento de dependencias e licencas. Projetos que nao solicitarem
essas bibliotecas nao devem adquiri-las como dependencias implicitas.

**Marco de verificacao:** um aplicativo puramente RS e outro que utilize
bibliotecas externas, ambos com builds reproduziveis e dependencias
inspecionaveis.

## Primeiro incremento desta estrategia

O modulo experimental ELF escrito em RS passa a permitir declaracoes
`seja` nos blocos `se`, `senao` e `enquanto`, com:
- visibilidade lexical (nome deixa de ser acessivel fora do bloco);
- sombreamento (nome interno pode ocultar e depois revelar o externo);
- espacos de pilha estaveis e exclusivos por declaracao;
- deteccao de redeclaracao no mesmo escopo e acesso a nome desconhecido;
- testes de execucao para binarios ELF64 O0/O8.

O emissor do subconjunto ainda precisa do compilador de desenvolvimento
Python para gerar seu proprio executavel, e nao representa um compilador
autocompilado completo.

## Regra de engenharia

Cada recurso novo deve ser implementado em ramo isolado, acompanhado
de testes automatizados que reproduzam o comportamento e casos de erro;
so integrar a `main` apos validacao completa. Preservar codigos,
arquivos e mensagens do projeto em portugues brasileiro sempre que nao
forem identificadores externos obrigatorios.
