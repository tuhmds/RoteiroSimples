# RS 0.41.3 — Sondagem nativa e desenrolamento de quadros grandes no Windows

## Objetivo e situação

A versão 0.41.3 mantém a geração direta de código de máquina da RoteiroSimples e amplia a descrição do estado da pilha de executáveis Windows x64. **Não introduz C, LLVM, Visual C++ ou runtime externo obrigatório.** O compilador continua implementado em Python; sua autocompilação em RS ainda está pendente.

A melhoria concreta é substituir a antiga reserva de pilha Windows em laço, cujo prólogo não podia ser descrito pela tabela de desenrolamento, por uma **sondagem em rotina folha própria, seguida de uma reserva única**.

## Como funciona

Para quadros menores que uma página, o prólogo permanece:

```asm
push rbp
mov rbp, rsp
push rbx
sub rsp, tamanho_do_quadro
```

Para quadros a partir de 4096 bytes, o gerador usa:

```asm
push rbp
mov rbp, rsp
push rbx
mov rax, tamanho_do_quadro
call rs_sondar_pilha
sub rsp, rax
```

A rotina interna `rs_sondar_pilha` inspeciona o caminho descendente da pilha em passos de 4096 bytes, incluindo o restante, para acionar as páginas de guarda necessárias antes da subtração final.

A rotina preserva **RAX e RSP** e modifica somente **R10 e R11**, registradores voláteis na convenção Windows x64. Ela não precisa reservar memória para chamadas do sistema, pois não chama APIs Windows. Por ser uma rotina folha sem mudança de RSP ou registradores não voláteis, não recebe uma entrada artificial de `.pdata` própria.

A sondagem permanece específica do Windows. O Linux conserva o mecanismo anterior de sondagem de páginas, o formato ELF64 PIE e a separação entre código e dados constantes.

## Informações de desenrolamento

O módulo `backend/desenrolamento_windows.py` confere os bytes emitidos pelo prólogo, a reserva real e o tamanho do quadro. Ele agora cobre quadros grandes representáveis, inclusive por meio das duas codificações existentes de `UWOP_ALLOC_LARGE`:

- `opInfo=0`: tamanho em unidades de oito bytes, até `65535 × 8`;
- `opInfo=1`: tamanho integral de 32 bits, usando dois slots adicionais.

O contrato exige quadros cujo tamanho seja congruente a oito módulo dezesseis, preservando o alinhamento esperado nas chamadas internas. Quando a forma do prólogo não coincide com a descrição, a geração recusa metadados inconsistentes, em vez de anunciar proteção inexistente.

Os arquivos PE continuam contendo uma tabela `.pdata`, um conjunto `.xdata` e diretório de exceções somente quando possuem entradas reais.

## Testes

Os testes cobrem:

- padrão de instruções da rotina de sondagem e preservação estrutural dos registradores;
- registro correto do prólogo da entrada principal e de funções com quadros grandes;
- quadros pouco acima de uma página e quadros na faixa de 600 mil bytes;
- codificação de `UWOP_ALLOC_LARGE` com um ou dois campos de tamanho;
- execução nativa em Windows para quadros grandes nos nove níveis de otimização;
- preservação da execução de programas com funções, arquivos e listas, via suíte completa de regressão;
- manutenção das proteções já existentes em PE e ELF.

As verificações estruturais não substituem testes de exceção real ou prova formal da ABI. A codificação x64 continua precisando de uma auditoria abrangente das demais rotinas auxiliares e dos prólogos não padronizados.

## O que NÃO está resolvido

**`HIGH_ENTROPY_VA` continua DESLIGADO.** A anomalia de fechamento de arquivos sob alta entropia, identificada nas versões 0.41/0.41.1, não foi atribuída de maneira conclusiva a uma causa raiz. Alterar a sondagem e melhorar o desenrolamento não demonstra que esse problema desapareceu. O Windows continua com `DYNAMIC_BASE`, tabela real de realocações e `NX_COMPAT`.

Ainda não há cobertura universal de `RUNTIME_FUNCTION` para todas as rotinas auxiliares com alocação/salvamento de registradores; tampouco há garantia completa de tratamento de exceções, Control Flow Guard ou segurança formal de memória. Os executáveis continuam experimentais.

## Próxima etapa indicada

Auditar explicitamente as rotinas auxiliares contra a convenção Windows x64, com foco em alinhamento antes de cada chamada externa, preservação de `RBX`, `RBP`, `RSI`, `RDI` e `R12`–`R15`, reserva de espaço de sombra e correspondência completa entre prólogos/epílogos e metadados. Só depois retestar a alta entropia em ambiente isolado com diagnóstico preciso.
