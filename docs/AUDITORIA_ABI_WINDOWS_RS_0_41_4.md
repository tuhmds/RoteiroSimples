# RS 0.41.4 — Auditoria da ABI Windows e desenrolamento de rotinas auxiliares

## Objetivo

Avançar na aderência do emissor nativo da RoteiroSimples à convenção de chamadas Windows x64, corrigindo um problema concreto de preparação da pilha nos caminhos fatais e descrevendo prólogos de rotinas auxiliares que já eram emitidos com quadros convencionais.

**Esta é uma ampliação de segurança verificável, não uma certificação de conformidade integral à ABI, de proteção contra corrupção de memória ou de aptidão para produção.** A sintaxe brasileira permanece inalterada, os executáveis continuam independentes de runtime Python/C/LLVM e a autocompilação ainda está pendente.

## 1. Saídas por erro

Antes da 0.41.4, alguns pontos de erro somente alinhavam RSP quando o programa utilizava listas, mesmo que a falha ocorresse com operandos temporários na pilha. Todos os caminhos fatais emitidos pela rotina principal Windows agora usam `preparar_saida_fatal_windows`:

- `and rsp, -16`: normaliza o alinhamento, mesmo após uma expressão ter empilhado temporários.
- `sub rsp, 48`: reserva espaço próprio para os quatro argumentos em registradores da ABI (32 bytes) e para o quinto argumento de `WriteFile` em `[rsp+32]`.
- A saída é **sem retorno**: o emissor imprime o diagnóstico e chama `ExitProcess`.

A correção vale para divisão por zero, estouro, recursão, índices, leitura, texto/UTF-8, bytes, listas, arquivos e código de saída inválido. O gerador Linux permanece inalterado.

A reserva é independente da estrutura do programa e impede que o diagnóstico dependa de um quadro de chamada que não lhe pertence. A alteração **não constitui prova** de ausência de todos os problemas de alinhamento em outras rotinas.

## 2. Prólogos auxiliares inspecionados

O módulo `backend/desenrolamento_windows.py` inclui `registrar_quadro_auxiliar`. O registro só é aceito se o código realmente contiver:

```text
push rbp
mov rbp, rsp
sub rsp, quantidade
...
mov rsp, rbp
pop rbp
ret
```

A reserva pode ser `imm8` ou `imm32` e precisa manter o alinhamento de 16 bytes após o salvamento de RBP. Os descritores `.xdata` usam `UWOP_ALLOC_SMALL` ou `UWOP_ALLOC_LARGE`, `UWOP_SET_FPREG` e `UWOP_PUSH_NONVOL`, conforme o tamanho real.

O código também verifica o epílogo, impedindo o registro de descrições incompatíveis com a sequência de instruções emitida. A geração de `.pdata` ordena os intervalos e recusa sobreposição.

As rotinas cobertas nesta etapa incluem:

- gravação e leitura histórica de arquivos;
- operações posicionais de gravação/leitura;
- abertura por caminho variável e abertura de recurso;
- leitura/gravação por identificador de recurso;
- publicação de arquivo por renomeação;
- liberação, movimentação e acréscimo em listas dinâmicas.

A entrada principal, funções de usuário e quadros grandes já tinham cobertura parcial estabelecida nas versões 0.41.2/0.41.3.

## 3. Auditoria das chamadas

As famílias registradas foram examinadas quanto ao prólogo, epílogo, reserva de pilha e retorno. A instrumentação inclui testes das tabelas geradas e da execução de arquivos, listas e diagnósticos.

**A RS mantém uma convenção interna própria para rotinas auxiliares**, diferente da convenção de argumentos dos serviços Windows. A responsabilidade de reservar o espaço de sombra, preservar os registradores não voláteis utilizados e alinhar a pilha nas chamadas ao sistema deve ser atendida por cada transição para a API do Windows.

Nem todas as rotinas auxiliares podem ser descritas com a regra de quadro atual. Por exemplo, algumas usam `sub rsp,40` diretamente sem salvar RBP; outras salvam `RSI`/`R13`–`R15` ou possuem múltiplos caminhos de retorno. **Elas não receberam metadados fictícios nesta alteração.**

Ainda são necessárias uma análise automatizada abrangente dos saltos e dos fluxos de pilha, validação interprocedural de registradores, testes reais de exceção no Windows e prova mais forte de preservação de convenções nas rotinas não cobertas.

## 4. Testes e rastreabilidade

A suíte `testes/test_quadros_auxiliares_rs0414.py` verifica:

- presença de registros para as famílias cobertas, com RVAs ordenados e não sobrepostos;
- correspondência dos bytes dos prólogos e epílogos com o contrato descrito;
- corrupção proposital de prólogo, que deve bloquear a geração de metadados;
- preparação correta da pilha e espaço de sombra nos pontos de erro;
- execução Windows de erros de aritmética, entrada e bytes em níveis de otimização distintos.

A suíte anterior continua verificando geração nativa, realocação, arquivos, recursos, funções, listas, sondagem e memória em Windows e Linux. Os registros históricos SHA-256 são preservados; os novos executáveis PE desta etapa são referenciados por `testes/fixtures/rs0414_binarios_08.json` e `rs0414_binarios_11.json`.

O aumento de cobertura em `.pdata`/`.xdata` muda legitimamente o tamanho e os hashes dos arquivos PE. Isso não deve ser confundido com redução de desempenho nem com alteração da sintaxe.

## 5. Limitações e próximas decisões

- `HIGH_ENTROPY_VA` permanece **desativado**, porque a falha observada no fechamento de arquivo ainda não teve sua causa raiz comprovada e eliminada.
- `DYNAMIC_BASE`, a realocação `DIR64` efetiva e `NX_COMPAT` permanecem habilitados.
- O Linux mantém PIE, segmento de dados somente leitura, segmento de código executável não gravável e pilha NX.
- A RS ainda não oferece desenrolamento universal de todas as rotinas auxiliares, mecanismo próprio de exceções ou garantias formais de segurança de memória.

**Próxima prioridade:** descrever/validar os auxiliares com prólogos diferentes e criar ensaios reais de `RtlVirtualUnwind` e preservação de registradores em situações de exceção. Somente depois reavaliar a alta entropia do Windows, com execução isolada e instrumentada.
