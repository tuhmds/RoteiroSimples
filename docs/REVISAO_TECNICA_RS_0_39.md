# Revisão técnica transversal da RS 0.39 — antes da RS 0.40

**Base inspecionada:** `8b576d7a2660421d83d9939dfea5a72cc5b820e0` (`main`, 12/10/2026).

**Método:** inspeção estática da estrutura de 201 entradas do repositório, código de compilação, tipos, geradores Linux/Windows, rotinas de arquivos, memória, biblioteca padrão, documentação, scripts de desempenho e testes. Consulta aos resultados da integração contínua: 367 testes por plataforma sem falhas, com 9 ignorados no Windows e 7 no Linux. **Não foi executada uma auditoria dinâmica completa nem provas de ausência de vulnerabilidades.** Hipóteses foram assinaladas, não apresentadas como falhas reproduzidas.

## 1. Resultado

A RS possui compilador nativo experimental com funcionalidades reais, mas a ampliação recente dos recursos de arquivos e tipos está à frente da integração com a representação intermediária e da disciplina de testes de segurança. Recomenda-se **RS 0.40 de estabilização**, não adicionar um motor de banco de dados ou nível novo de otimização.

### P0 — corrigir antes de ampliar tipos compostos ou persistência

**P0-01 — largura inconsistente para registros binários dentro de listas dinâmicas (incompatibilidade confirmada por leitura de código; efeitos em execução ainda a reproduzir).**

- `backend/x86_64.py`, `_palavras_tipo`: `bytes[N]` ocupa `1 + ceil(N/8)` palavras.
- `backend/listas_dinamicas.py`, `largura_elemento`: o cálculo de `palavras` reconhece `lista` e `texto`, mas não `bytes`; usa uma única palavra para `bytes[N]`.
- `compilador/parser.py` admite `bytes[N]` como campo de registro, e listas dinâmicas admitem elementos do tipo registro. Portanto, os dois módulos podem discordar quanto ao espaço reservado e copiado.
- **Risco:** truncamento de elementos, cópia fora de sua região e inconsistência dos dados. Não afirmar exploração ou corrupção observada sem reprodução.
- **Correção:** criar uma descrição canônica de layout/alinhamento/tamanho de tipo consumida por *todos* os módulos. Testar `lista[Registro]` com campos `bytes[1]`, `bytes[8]`, `bytes[9]`, `bytes[16]`, `bytes[64]` e registros aninhados, inclusive comparação após realocação e cópia de volta. Testes nativos Linux/Windows em O0/O8.

**P0-02 — a política de caminhos seguros não alcança todas as APIs legadas de arquivo.**

- `backend/arquivos_posicionais.py` abre caminhos usando, no Linux, `O_WRONLY|O_CREAT` ou `O_RDONLY`, sem `O_NOFOLLOW`, ao contrário do novo `backend/arquivos_abertos.py`.
- O tratamento seguro de nomes por literal/variável não garante confinamento em um diretório confiável e não impede que a API antiga siga enlaces simbólicos.
- **Risco:** se o diretório de execução tiver entradas controláveis por terceiros, um programa pode modificar dados fora do local esperado.
- **Correção:** definir uma política uniforme de resolução de caminhos para todas as operações de arquivo. Preferir diretório-base identificado e resolução protegida; tratar Linux/Windows explicitamente. Testar symlinks/reparse points e corridas de nomes. Não anunciar sandbox apenas porque um nome é relativo.

### P1 — endurecer a plataforma e o contrato antes de chamá-la estável

**P1-01 — executáveis nativos ainda carecem de endurecimento moderno.**

- `backend/linux_elf.py` produz ELF `ET_EXEC` com entrada fixa em `0x400000`, um segmento carregável, sem `PT_GNU_STACK` explícito: não produz PIE nem solicita explicitamente política de pilha não executável.
- `backend/windows_pe.py` fixa a base `0x140000000`, não emite seção/tabela `.reloc` nem habilita `DYNAMIC_BASE` nas características DLL. A marca NX_COMPAT atual não substitui ASLR.
- **Correção:** planejar suporte real a PIE/ASLR e relocação (não basta ligar uma flag), declarar proteção da pilha e conferir cabeçalhos com validadores de PE/ELF nos testes. Validar Win64 ABI, alinhamento, seções e execução.

**P1-02 — representação intermediária incompleta em relação à sintaxe nova.**

- `compilador/ir.py` converte um conjunto antigo de nós (`atribua`, `texto`, `lista`, `se`, `enquanto`, `para` etc.), mas não instruções modernas de `bytes`, arquivos abertos, publicação ou várias operações de listas dinâmicas.
- `backend/__init__.py` usa adequadamente o gerador conservador nesses casos, mas a escolha reduz a cobertura das otimizações O1–O8 e várias ferramentas de análise não servem aos programas mais novos.
- `compilar.py` rejeita algumas opções avançadas em funções e escopos, mas não mantém uma matriz pública completa de operações suportadas pela IR.
- **Correção:** contrato AST/IR com verificação exaustiva de nós e efeitos, identificação transparente de rebaixamentos e testes de equivalência semântica. Não adicionar O9 antes de resolver.

**P1-03 — concorrência de arquivos continua parcial.**

- `backend/arquivos_abertos.py` usa `flock` cooperativo no Linux e acesso exclusivo por abertura no Windows; `backend/publicacao_atomica.py` substitui nomes após preparação/sincronização.
- Bloquear o provisório **não serializa** escritores concorrentes que disputem o nome publicado; leitores abertos podem manter a versão antiga após a substituição.
- No Linux, a troca pode ter ocorrido mesmo se falhar o `fsync` do diretório; o retorno -9 não é rollback.
- **Correção:** especificar arquivo de controle comum, contrato de leitores e escritores, teste multiprocesso concorrente, recuperação após falhas de syscall e política de repetição idempotente.

**P1-04 — limites de memória e recursos precisam ser formais.**

- `compilador/parser.py` permite capacidades estáticas muito grandes, enquanto `backend/x86_64.py` aloca os valores locais no quadro de pilha. Já existe sondagem de páginas, o que é positivo; isso **não elimina** esgotamento do limite de pilha.
- `compilador/tipos.py` ainda exporta `MAX_VARIAVEIS=256`, embora a validação real de tamanho esteja em `compilador/semantica.py` pelo quadro em bytes: evitar parâmetros legados que induzam a erro.
- **Correção:** orçamento de pilha explícito, regra de transferência para heap ou erro compreensível para buffers enormes, testes em Windows/Linux e documentação de custos.

### P2 — lacunas de linguagem e biblioteca que limitam aplicações cotidianas

**P2-01 — tipos fundamentais:** ainda não há `real` nem decimal exato, texto dinâmico geral, bytes dinâmicos e um modelo completo de referências mutáveis. Para dinheiro, priorizar inteiro em centavos ou tipo decimal com escala explícita, sem usar real binário ingenuamente.

**P2-02 — expressões:** `compilador/expressoes.py` suporta aritmética e comparações, mas não operadores booleanos curtos `e`, `ou`, `nao`; também falta especificar precedência e avaliação curta de condições compostas. Introduzir com critérios de efeitos e testes.

**P2-03 — coleções e bibliotecas:** `biblioteca_padrao/listas.rts` e `estatistica.rts` possuem várias operações fixadas artificialmente a cinco elementos. Migrar algoritmos para coleções tipadas arbitrárias, empréstimos de leitura e resultados tipados, sem quebrar antigos programas sem estratégia de compatibilidade.

**P2-04 — erros e arquivos:** recursos antigos usam códigos inteiros; a biblioteca `biblioteca_padrao/arquivos.rts` faz uma conversão opcional para `resultado[inteiro]`. Unificar o contrato em longo prazo, mantendo erros de sistema específicos e o fato de que operações podem ter efeitos parciais. Não confundir `encerre()` com finalização segura de transações.

**P2-05 — interoperabilidade:** não existe ainda interface de funções externas estabilizada para SQLite, PostgreSQL, MariaDB e bibliotecas de sistema. Projetar uma fronteira `inseguro`/ABI C isolada, sem exportar ponteiros crus ao código RS normal.

### P2 — engenharia e experiência de desenvolvimento

- **Integração contínua:** `.github/workflows/testes.yml` executa unittest em Windows/Linux apenas com Python 3.11. O README afirma Python 3.10+; a matriz deveria verificar também a versão mínima, além de regressões de execução nativa.
- **Testes:** 367 por plataforma são avanço real, mas não há evidência de cobertura de código, fuzzing estruturado, testes de estresse prolongados ou injeção de falhas do sistema operacional. Priorizar testes diferenciais O0–O8, geradores de programas válidos e entradas binárias, corpus reproduzível e controle de sementes.
- **Desempenho:** `benchmarks/medir.py` mede O3–O6, não cobre O0, O7 ou O8 e ainda identifica o projeto como RS 0.16. Não extrapolar os resultados para o compilador atual; medir workloads com funções, listas, texto, bytes e arquivos, documentando fallback conservador.
- **Distribuição e projeto público:** a árvore atual não inclui manifesto `pyproject.toml`, licença explícita ou processo de versões marcadas. Adicionar instalação reprodutível, licença escolhida conscientemente, exemplos de erros úteis, documentação de semântica e suporte inicial ao editor.
- **Arquitetura do código:** `compilador/parser.py` concentra muitas responsabilidades sintáticas/semânticas; `backend/x86_64.py` combina emissão de operações de alto nível, rotinas de sistema e gerenciamento de recursos. Separar por responsabilidades e melhorar os contratos entre módulos antes de crescer indefinidamente.

## 2. O que preservar

- Emissão direta de executáveis ELF/PE sem ferramenta externa obrigatória.
- Sintaxe e mensagens em português brasileiro, com palavras reservadas sem acentos.
- Propriedade única de recursos, limites de índices, detecção de estouro aritmético e erros recuperáveis.
- Geração conservadora ao usar recursos ainda não suportados integralmente pela IR, com opção `--mostrar-estrategia`.
- Testes de aplicações reais nos dois sistemas e comparação de resultados de otimização.
- Biblioteca padrão desenvolvida na própria RS sempre que tecnicamente possível.

Essas qualidades fazem parte da identidade do projeto; **segurança não exige descartar a arquitetura atual**.

## 3. Plano recomendado e critérios de aceite

| Etapa | Prioridade | Conclusão verificável |
|---|---|---|
| RS 0.40A — integridade | P0-01/P0-02 | Layout único, testes de registros binários em listas e política de caminhos consistente em todas as APIs |
| RS 0.40B — testes e transparência | P1-02/CI | Declaração explícita de suporte IR por recurso, erros úteis para análises indisponíveis e testes diferenciais/propriedades |
| RS 0.41 — plataforma segura | P1-01/P1-04 | PIE/ASLR conforme alvo, pilha protegida/verificada e política clara de alocação |
| RS 0.42 — ergonomia | P2-01 a P2-04 | Operadores booleanos, coleções genéricas, tipos necessários ao cadastro, padronização de erros |
| RS 0.43 — integração | P2-05 | Ponte ABI com ao menos um uso real e testes de falhas do limite externo |
| Dados RS: núcleo de referência | Depois dos bloqueios | Dois programas RS compartilham registros persistentes versionados, recuperam os dados após reinício e rejeitam corrupção com diagnóstico, sem alegar ACID |

A numeração representa proposta de roteiro, não promessa de que todos os marcos cabem obrigatoriamente em uma só versão. Não aumentar números de otimização por marketing. Corrigir riscos de dados e estruturar a linguagem é mais valioso que acrescentar comandos isolados.

## 4. Critério para chamar uma falha de confirmada

1. Criar programa RS mínimo e repetível que acione o caso.
2. Executá-lo isoladamente em Linux e Windows quando aplicável.
3. Confirmar o resultado esperado e o observado, inclusive bytes e código de retorno.
4. Corrigir sem alterar comportamento de casos existentes.
5. Acrescentar regressão em O0 e O8; para casos de optimizer, ampliar até O0–O8.
6. Só integrar à `main` depois de CI verde.

A presente revisão identifica com alta confiança divergências de código e lacunas documentais, **mas não substitui essas etapas de comprovação**.
