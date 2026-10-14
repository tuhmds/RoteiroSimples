# Como contribuir para a RoteiroSimples (RS)

Obrigado pelo interesse na RS. Este é um projeto **experimental** de linguagem de programação em português brasileiro, com geração de executáveis nativos. A colaboração é bem-vinda, sobretudo revisões críticas fundamentadas, testes adversariais e sugestões arquiteturais.

## Antes de propor mudanças

- Leia [Princípios permanentes da RS](docs/PRINCIPIOS_RS.md), o [README](README.md) e a [orientação para revisão técnica](docs/CONVITE_REVISAO_TECNICA_COMPILADOR.md).
- **Não envie alterações diretamente à `main`.** Trabalhe em uma ramificação própria (`revisao/...`, `correcao/...`, `melhoria/...`) ou fork, conforme o acesso disponível.
- Abra uma **solicitação de incorporação (pull request, PR)** com descrição, riscos, testes e justificativa. O mantenedor `@tuhmds` deverá analisar e aceitar a mudança antes de incorporá-la.
- Não faça incorporação automática, reescrita forçada do histórico, exclusão de ramificações ou alterações de segurança/configuração sem concordância do mantenedor.
- **Importante:** este documento define o processo de trabalho, mas **não é uma barreira técnica**: a obrigatoriedade depende da proteção da ramificação `main` nas configurações do GitHub. Enquanto ela estiver desprotegida, uma pessoa com acesso de escrita ainda poderá enviar mudanças diretamente.

## Convenções do projeto

1. Sintaxe, palavras-chave, tipos, funções, variáveis, mensagens de erro, testes, exemplos e novos nomes internos em português brasileiro. **Identificadores da sintaxe não levam acentos**; documentação e mensagens podem usar acentos.
2. Manter as interfaces obrigatórias dos sistemas operacionais nos nomes externos originais; arquivos convencionais exigidos pelo GitHub são exceção justificada.
3. O compilador de desenvolvimento ainda é escrito em Python. Ele emite código x86-64 **diretamente** em formatos PE32+/Windows e ELF64/Linux, sem exigir C, LLVM ou montador externo. Os executáveis gerados não dependem do Python, mas dependem das interfaces dos sistemas operacionais.
4. Evitar criar dependências obrigatórias de compilação ou execução sem discussão arquitetural. Propostas de interoperabilidade devem ser opcionais, isoladas e justificadas.
5. Preservar a semântica de erros observáveis, memória/propriedade, tipos, limites, ordem de avaliação e convenções de chamada.
6. Não apresentar protótipos como recursos completos ou resultados de desempenho sem medição reproduzível.

## Conteúdo mínimo de cada PR

- Qual problema concreto resolve; alternativa considerada; mudança proposta.
- Qual parte afeta: análise lexical, sintaxe, tipos, semântica, AST, IR, CFG, SSA, otimização, geração de máquina, ABI, memória, biblioteca, testes ou documentação.
- Compatibilidade: o que permanece igual e o que muda no comportamento observável.
- Evidências: testes automatizados, caso de reprodução, plataformas usadas, comandos executados e resultados; quando pertinente, comparação de executáveis gerados em `-O 0` a `-O 8`.
- Riscos e limitações remanescentes.
- Indicação de uso de IA no trabalho, se houver: como foi utilizada e quais verificações humanas/técnicas foram feitas.

Testes básicos: `python -m unittest discover -s testes`, além das verificações específicas propostas e da integração contínua em Windows/Linux. Confira as exigências reais de cada revisão: testes dependentes de plataforma podem ser ignorados fora de seu sistema.

## Uso responsável de IA

A RS vem sendo desenvolvida com apoio de inteligência artificial para concepção, programação, revisão, documentação e criação de testes. Isso **não substitui** a demonstração de correção, a revisão independente, os testes adversariais ou a decisão humana. Não trate código gerado por IA como validado apenas por ter sido gerado. Declare incertezas e resultados não reproduzidos.

## Primeiro tipo de contribuição desejado

Uma auditoria independente da arquitetura do compilador, com defeitos ou lacunas priorizados por **gravidade, evidência, risco e custo de correção**. Pode começar por um *issue* ou discussão, sem escrever código. Correções pequenas e demonstráveis são preferíveis a reestruturações grandes sem provas.

## Acesso e segurança

O repositório é privado neste estágio. Não publique nem redistribua seu conteúdo sem autorização do mantenedor. Credenciais, dados de acesso e arquivos locais não devem entrar em commits. Propostas não devem incluir código com licença incompatível nem trechos de terceiros sem permissão.

Em repositórios privados pertencentes a contas pessoais, o GitHub concede acesso de escrita a colaboradores convidados. Portanto, **somente a regra de proteção da `main` com PR, revisão obrigatória do responsável e verificação da integração contínua torna o fluxo obrigatório**; o arquivo `.github/CODEOWNERS` ajuda a solicitar revisão, mas não bloqueia nada isoladamente.
