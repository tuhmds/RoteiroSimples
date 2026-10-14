# Convite à revisão técnica do compilador RoteiroSimples (RS)

## O que estamos construindo

A **RoteiroSimples (RS)** é uma linguagem de programação experimental com sintaxe em português brasileiro, concebida para ser acessível a iniciantes **sem renunciar** a uma arquitetura de compilação nativa, a tipos bem definidos e a verificações de segurança e correção. Os identificadores da sintaxe não levam acentos; textos de usuário e documentação podem conter acentuação.

Nosso diferencial pretendido não é apenas traduzir palavras-chave: queremos **uma linguagem completa, utilizável e capaz de formar sua própria cadeia de ferramentas**, sem depender obrigatoriamente de C, LLVM ou de um montador externo na geração de executáveis. Essa independência é um **objetivo de engenharia progressivo**, não uma alegação de autocompilação já concluída.

## Estado verificável — RS 0.42O (outubro de 2026)

- O **compilador de desenvolvimento é escrito em Python**. Ele analisa fontes `.rts` e emite diretamente código de máquina x86-64 e executáveis PE32+ para Windows ou ELF64 para Linux. A execução dos binários gerados não exige Python; eles usam serviços do sistema operacional.
- Há análise lexical, árvore sintática, verificação semântica/tipos, representações intermediárias, grafos de fluxo de controle, análises de efeitos e de fluxo de dados, construção SSA e caminhos de alocação de registradores/geração nativa para subconjuntos elegíveis.
- Há gerenciamento de memória/propriedade para textos, bytes, listas e registros, com transferência explícita, empréstimos de leitura, resultados tipados e arquivos. Há um caminho conservador para partes do programa ainda não suportadas pela representação otimizada.
- O trabalho inclui ABI Windows/Linux, testes de desenrolamento de pilha e regressões, campanhas diferenciais e integração contínua em Windows/Linux.
- A RS 0.42O inclui operadores `e`, `ou` e `nao` com curto-circuito e regras de precedência. O projeto também experimenta bibliotecas em RS e armazenamento persistente simples, **sem reivindicar ACID ou uso em produção**.
- A cadeia ainda **não é autocompilada**. Recursos como números reais completos, ampliação da IR/SSA de operações proprietárias e com arquivos, uma biblioteca padrão mais ampla e um ambiente de desenvolvimento amigável ainda exigem trabalho. Não recomendamos uso em produção.

**Entradas para auditoria:** [README](../README.md), [princípios do projeto](PRINCIPIOS_RS.md), [SSA das funções escalares na 0.42L](SSA_FUNCOES_RS_0_42L.md), [consolidação e testes na 0.42J](CONSOLIDACAO_RS_0_42J.md), [operações lógicas na 0.42O](OPERADORES_LOGICOS_RS_0_42O.md), `compilador/`, `backend/`, `testes/` e `.github/workflows/testes.yml`.

## Como desenvolvemos — transparência sobre a IA

Estamos usando **inteligência artificial como ferramenta ativa** de projeto, implementação, revisão, testes e documentação. Não escondemos esse processo nem reivindicamos que a IA substitui experiência humana em compiladores. Buscamos exatamente o contrário: críticas humanas independentes que exponham decisões frágeis, desvios conceituais e falhas que os nossos próprios testes não captaram. A validação exige evidências reproduzíveis, e as decisões de incorporação são dos mantenedores.

## Onde queremos chegar

1. Consolidar semântica, sistema de tipos, escopos, funções, propriedade e tratamento de erros, removendo limitações artificiais sem perder segurança.
2. Reduzir duplicação entre caminhos de geração conservador e otimizado; melhorar a representação intermediária para suportar cada vez mais recursos de forma consistente.
3. Evoluir o gerador nativo, ABI, alocação e otimizações com benchmarks confiáveis e verificações diferenciais.
4. Construir bibliotecas padrão, ferramentas de dados e aplicações escritas na própria RS.
5. Construir o **RS Studio**, com orientação ao iniciante e diagnósticos didáticos.
6. No longo prazo, avançar em direção a um compilador escrito na própria RS, com estratégia explícita de autocompilação e reprodução de binários.

## O parecer técnico que gostaríamos de receber

Adilson, por sua experiência com compiladores, queremos pedir uma análise crítica — **sem obrigação de escrever código**. Em especial:

1. **Arquitetura:** a separação atual entre analisador, semântica, IR, CFG, SSA, otimização, gerador e runtime nativo é adequada? Há acoplamentos ou duplicações que se tornarão bloqueios?
2. **Representação intermediária:** como reduzir a lacuna entre os subconjuntos otimizados em SSA e o caminho conservador, sem tornar a implementação impraticável?
3. **Tipos, propriedade e efeitos:** quais invariantes precisam de contrato mais rigoroso ou demonstração de correção para evitar uso após movimentação, empréstimo inválido, vazamentos ou mudanças de comportamento com otimização?
4. **Geração nativa e ABI:** que testes adversariais você priorizaria para Windows/Linux, alocação de registradores, pilha, desenrolamento e convenções de chamada?
5. **Qualidade e segurança:** o que faltaria para chamar isso de compilador tecnicamente robusto? Quais testes diferenciais, fuzzing, propriedades formais, cobertura de IR e cenários de falha têm maior retorno?
6. **Autocompilação:** que sequência de etapas tornaria realista passar do compilador em Python a uma implementação em RS, preservando a independência desejada?
7. **Direção do projeto:** quais escolhas atuais você manteria, quais reconsideraria e quais três problemas atacaria primeiro? Gostaríamos de ouvir críticas, inclusive às premissas de projeto.

Idealmente, classifique suas observações em **bloqueantes**, **importantes**, **melhorias** e **perguntas em aberto**, citando exemplos ou reproduções sempre que possível.

## Acordo de colaboração

A contribuição ideal começa por um parecer ou proposta em *issue*. Quando houver código, o fluxo preferido no repositório público é: **fork próprio → ramificação de trabalho → pull request → revisão do mantenedor antes de incorporar na `main`**. Um fork não exige acesso de escrita ao repositório original.

Critérios de integração: comportamento observável preservado ou alteração intencional documentada, testes reprodutíveis, avaliação de riscos e revisão técnica. Não se espera aprovação automática.

A equipe utiliza IA intensamente, mas dá valor especial à crítica humana independente. Não queremos apenas elogios: queremos saber **onde estamos errando, quais riscos ainda não percebemos e como transformar a RS num compilador sério**.

A proteção obrigatória da `main` depende das regras do GitHub; um texto de colaboração não equivale a uma barreira técnica.
