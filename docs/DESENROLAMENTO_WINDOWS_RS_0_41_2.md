# RS 0.41.2 — Metadados reais de desenrolamento Windows x64

## Objetivo

Construir uma etapa verificável da compatibilidade da RoteiroSimples com a ABI Windows x64: descrever os quadros de pilha que o compilador realmente gera e produzir entradas válidas no diretório de exceções do PE32+.

Os executáveis continuam gerados diretamente pelo emissor nativo da RS, sem etapa obrigatória em C, LLVM ou biblioteca de execução externa. O compilador de desenvolvimento ainda utiliza Python; **a autocompilação continua pendente**.

## Implementação

A versão introduz `backend/desenrolamento_windows.py`, que recebe as posições dos prólogos emitidos e gera:

- uma tabela `.pdata` de estruturas `RUNTIME_FUNCTION` (RVA inicial, RVA final e RVA de descrição), ordenadas e sem sobreposição;
- uma região `.xdata` com estruturas reais `UNWIND_INFO`, alinhadas a quatro bytes;
- informações `UWOP_PUSH_NONVOL` para o salvamento de `RBP` e `RBX`, `UWOP_SET_FPREG` para `mov rbp, rsp` e `UWOP_ALLOC_LARGE` para a reserva fixa;
- um diretório `IMAGE_DIRECTORY_ENTRY_EXCEPTION` que aponta efetivamente para a tabela `.pdata`.

A geração verifica **os bytes reais** dos prólogos e o tamanho do quadro: se os padrões mudarem sem atualizar o contrato, ela rejeita a descrição, em vez de produzir informações falsas.

São registradas a entrada principal e funções RS com quadros fixos elegíveis. As posições são obtidas dos rótulos do emissor, e permanecem corretas mesmo quando a disposição do código muda durante as otimizações existentes.

## Restrições deliberadas

**A cobertura é parcial.** Quadros com sondagem de pilha de 4096 bytes ou mais não recebem entradas falsas na tabela, porque seu prólogo inclui alocações por etapas ainda não descritas por este formato. As rotinas auxiliares de E/S, listas e arquivos também não são cobertas integralmente por `RUNTIME_FUNCTION`.

Isso significa que a RS **ainda não possui desenrolamento Windows completo** nem tratamento seguro e abrangente de exceções durante qualquer ponto de execução.

A ABI Windows x64 também exige atenção adicional a:

- alinhamento da pilha em 16 bytes nas chamadas;
- reserva de 32 bytes para os argumentos em registradores da API externa (*espaço de sombra*);
- preservação de registradores não voláteis como `RBX`, `RBP`, `RSI`, `RDI` e `R12`–`R15`;
- documentação correta de todas as transições de prólogo e epílogo e dos quadros com sondagem;
- testes de desenrolamento em exceções, não apenas inspeção de bytes.

Os testes desta versão exercitam funções aninhadas, recursão, arquivos e diferentes níveis de otimização; **não constituem prova de conformidade ABI universal**.

## Segurança de execução

A RS 0.41.2 conserva `DYNAMIC_BASE` e `NX_COMPAT` no Windows. `HIGH_ENTROPY_VA` permanece **desligado**, pois a RS 0.41.1 documentou uma violação de acesso na sequência de fechamento de arquivos. A existência de `.pdata` e `.xdata` para determinados quadros, isoladamente, **não prova que a incompatibilidade esteja resolvida**.

No Linux, permanecem o ELF64 PIE, o segmento de código executável e não gravável, os dados constantes somente para leitura e a pilha não executável.

## Testes

`testes/test_desenrolamento_windows_rs0412.py` verifica:

1. Os bytes de prólogo, a reserva do quadro e os rótulos de entrada, saída e término do prólogo.
2. A presença de `.pdata` e `.xdata`, seus tamanhos, alinhamentos, intervalo de RVAs e organização do diretório de exceções.
3. A codificação dos cinco slots de `UNWIND_CODE` e das instruções que eles descrevem.
4. O comportamento explícito de ausência de metadados para quadros grandes ainda não suportados.
5. A recusa de prólogos incompatíveis com as regras declaradas.
6. A execução de aplicações nativas com funções e arquivos no Windows nos níveis `-O 0`, `-O 4` e `-O 8`.

Os registros binários de versões anteriores são preservados. A série nova de referências em `testes/fixtures/rs0412_binarios_*.json` acompanha as alterações do formato PE. A integração contínua precisa terminar sem falhas nos dois sistemas antes da fusão com a ramificação principal.

## Próximas correções prioritárias

Ampliar a auditoria de registradores não voláteis usados pelos caminhos SSA, padronizar prólogos das rotinas auxiliares e a sondagem de quadros grandes, e realizar testes reais de exceção/desenrolamento. Somente depois disso retestar alta entropia com instrumentação controlada.

Fonte de referência externa: Microsoft Learn, documentação de convenções de chamadas x64, prólogos/epílogos e informações de desenrolamento/ `RUNTIME_FUNCTION`.

A RS continua **experimental** e não deve ser anunciada como adequada a produção.
