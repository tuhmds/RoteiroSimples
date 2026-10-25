# Revisão estrutural e refatoração da RoteiroSimples

**Levantamento inicial:** 24 de outubro de 2026. **Escopo:** árvore `main`
no commit `692643df`, antes de qualquer integração desta revisão.

## Objetivo

Simplificar a implementação sem alterar, por acidente, a semântica da
linguagem, a representação de dados, a ABI, o formato de executável ou
os diagnósticos públicos. Cada transformação precisa ser pequena,
revisável, testável e reversível por um commit, com evidência de que
continua correta no Windows e no Linux.

"Remover vestígios de IA" significa **retirar código desnecessário,
comentários automáticos imprecisos, redundância e estrutura sem justificativa**.
Não significa inventar autoria humana, apagar fatos de procedência ou
reescrever código apenas para fazê-lo parecer diferente. Contribuições
humanas e revisões externas devem ser creditadas corretamente.

## Inventário verificado

A API de árvore do GitHub indicou 494 arquivos versionados, cerca de
3,06 MB no total, incluindo:

| Área | Arquivos | Bytes |
|---|---:|---:|
| `compilador/` | 41 | 321035 |
| `backend/` | 24 | 240151 |
| `biblioteca_padrao/` | 40 | 416048 |
| `testes/` (inclui fixtures) | 152 | 1292366 |
| `docs/` | 111 | 546745 |
| `exemplos/` | 85 | 70340 |

Alguns módulos que concentram responsabilidades:

- `backend/x86_64.py`: cerca de 94 KB, 1835 linhas antes desta PR,
  com geração de instruções, organização do programa, rotinas de
  recursos e saídas fatais.
- `compilador/parser.py`: cerca de 65 KB, 996 linhas; análise
  sintática, tipos, declarações e controle concentrados na mesma função.
- `biblioteca_padrao/emissao_corpos_funcoes_elf.rts`: cerca de 89 KB;
  continuação importante da cadeia de compilação escrita em RS.
- `testes/test_emissao_corpos_funcoes_elf_rs.py`: cerca de 83 KB;
  grande concentração de cenários do emissor.

**Levantamento, não conclusão:** tamanho isolado não prova defeito.
O risco é o acoplamento e o custo de revisar mudanças sem regressões.

## Problemas e riscos prioritários

1. **AST histórica baseada em tuplas marcadas.** Em
   `compilador/ast.py`, `NoExpressao` e `NoInstrucao`
   continuam subclasses de `tuple`. Há consumidores por índice e
   por etiqueta textual. A migração deve ter representação tipada,
   contrato de serialização e testes diferenciais antes da troca.
2. **Parser concentrado.** Isolar análise léxica, sintaxe, construção
   de nós, atribuição de tipos e verificação de propriedade em
   interfaces independentes, **sem manter dois parsers ativos de
   forma indefinida**.
3. **Backend AMD64 com emissões repetidas.** Vários grupos de erros
   duplicavam alinhamento Win64, impressão e término. Esta PR extrai
   a rotina única `_emitir_erro_fatal` e preserva ordem e rótulos.
4. **Dois percursos de geração nativa.** Convergir contratos de IR,
   ABI e suporte funcional; nunca descartar fallback antes de
   demonstrar equivalência e manter todas as características atuais.
5. **Cadeia de compilação ainda depende de Python.** Continuar
   componentes escritos em RS, sem trocar uma dependência temporária
   por Rust ou Go obrigatórios. Uma implementação Rust paralela pode
   servir de oráculo independente para a migração do front-end.
6. **Proliferação documental e rastreabilidade.** Consolidar contratos
   vivos, preservar documentos históricos como histórico e evitar
   duplicar especificações incompatíveis.

### Observações para não propagar diagnósticos ultrapassados

- `compilador/lexico.py` já guarda linha e coluna dos tokens;
  `Token` herda de `str`, mas tem `.origem`.
- `MAX_VARIAVEIS=256` permanece por compatibilidade, mas **não**
  restringe o total de variáveis do programa.
- `docs/LINGUAGEM_RS.md` já consolida o contrato experimental
  da RS 0.42U.
- A biblioteca `biblioteca_padrao/lexico.rts` já implementa uma
  etapa de análise léxica escrita na própria RS.

## Sequência de execução

### Passada 1 — preservar, medir e eliminar redundância

- Criar baseline em CI para Linux/Windows, O0/O8 e exemplos.
- Extrair trechos repetidos sem alterar ordem das instruções ou
  política de recursos; adicionar testes de contrato.
- Revisar importações, constantes, nomes, efeitos colaterais e
  lógica morta **somente após rastrear referências**.
- Medir tamanho de binário, tempo de compilação, tempo de execução
  e diagnósticos relevantes antes/depois.

**Critério de conclusão:** suíte verde nas plataformas, nenhuma regressão
conhecida de ABI, erro, memória ou desempenho; PRs separados por subsistema.

### Passada 2 — fronteiras claras

- Separar AST, parser, semântica e propriedade; classes/enumerações
  tipadas com adaptador de compatibilidade temporário.
- Isolar decisões de ABI e layout do emissor de instruções.
- Centralizar contratos de E/S, arquivos, buffers, UTF-8 e ownership.
- Remover duplicações **apenas** quando os casos observáveis forem iguais.

**Critério:** testes de equivalência da AST e de erros/posições,
oráculos independentes e testes negativos de propriedade e limites.

### Passada 3 — simplificação do compilador e da biblioteca

- Convergir IR/CFG/SSA e selecionar caminhos otimizados por capacidade
  comprovada, sem redução silenciosa de recursos.
- Consolidar bibliotecas escritas em RS e fortalecer segurança e
  tratamento explícito de falhas.
- Tratar código não utilizado com cobertura, buscas e testes antes
  da exclusão; não presumir que "não chamado por um teste" é morto.

**Critério:** mesmo comportamento dos programas existentes,
consistência em erros, protocolos e binários nos alvos aplicáveis.

### Passada 4 — autocompilação e revisão externa

- Comparar lexer/parser da RS, da implementação Python e, caso o
  colaborador entregue, da implementação Rust.
- Ampliar o compilador em RS até atingir recursos reais necessários
  para compilar seu próprio código, com testes de bootstrap.
- Rever resultados de forma independente, inclusive fuzzing,
  Unicode, limite de memória e casos malformados.

**Critério:** autocompilação reproduzível e documentada, sem afirmar
independência total antes de remover a necessidade de Python no
desenvolvimento.

## Regras para cada PR

- **Uma responsabilidade por mudança.** Não migrar AST, ABI e arquivo
  de persistência juntos.
- **Preservar compatibilidade por padrão.** Mudança de semântica exige
  proposta explícita, migração, testes e documentação.
- **Não esconder falhas.** Não desabilitar testes, remover asserções
  ou alterar expectativas apenas para "ficar verde".
- **Código em português brasileiro no domínio RS**, exceto contratos
  externos e APIs cujo nome original seja obrigatório.
- **Sem ornamentação.** Comentários explicam invariantes e decisões,
  não narram linha a linha o que o código já diz.
- **Segurança e correção primeiro.** Enxugar não pode retirar
  validações de índices, vida útil, overflow ou alinhamento de ABI.
- **Integrar somente após CI.** Revisar, medir e mesclar PR por PR;
  branches simultâneas devem evitar as mesmas áreas.

## Primeira PR desta revisão

`refatoracao/01-saidas-fatais-amd64` concentra emissão repetida
de diagnósticos fatais em `backend/x86_64.py`, sem alterar
rótulos, textos ou o tratamento de Windows/Linux. Um teste unitário
verifica a ordem e os opcodes de encerramento. A suíte nativa inteira
continua sendo necessária para confirmar a ausência de regressões.
