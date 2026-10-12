# RS 0.41.5 — Ensaios reais de desenrolamento Windows

## Resultado da revisão

A revisão usa o desenrolador do próprio Windows AMD64 para verificar o código de máquina e as seções `.pdata`/`.xdata` efetivamente publicadas pelo compilador. Também executa exceções de ponto de parada e retornos normais em processos isolados. O ensaio não exige SDK, C, LLVM, montador ou runtime adicional nos executáveis RS.

Foram corrigidos três problemas concretos: a recuperação incorreta de `RBX` quando o corpo mantinha operandos temporários na pilha; epílogos auxiliares não reconhecidos pelo Windows; e a passagem de um ponteiro supostamente nulo cuja metade superior não havia sido zerada. A cobertura passou de 12 para 22 rotinas auxiliares.

## 1. Quadro de usuário e registradores

A entrada principal e as funções Windows salvam `RSI`, `RDI`, `R12`, `R13`, `R14`, `R15`, `RBX` e `RBP`, nessa ordem, antes de estabelecer `RBP`. As descrições incluem cada `UWOP_PUSH_NONVOL` e o `UWOP_SET_FPREG` correspondente aos limites reais das instruções.

O formato anterior salvava `RBX` depois de estabelecer o quadro. Com `RSP` reduzido por temporários, o desenrolador recuperava `RBX` antes de reconstruir a pilha a partir de `RBP`, usando um endereço errado. Salvar todos os registradores antes do estabelecimento do quadro elimina esse problema e permite recuperar o contexto do chamador com temporários vivos.

Os locais conservam seus deslocamentos negativos históricos. No Windows, o orçamento de pilha passou a `RBP+72`, o ponteiro oculto de retorno a `RBP+80` e os argumentos começam em `RBP+80` ou `RBP+88`, conforme o tipo de retorno. Isso inclui o encaminhamento de retornos compostos entre funções. A convenção interna de argumentos da RS permanece própria; as transições para serviços Windows atendem à ABI do sistema.

O validador também examina o trecho de controle de profundidade entre os salvamentos e a reserva. Uma alteração que introduza um `PUSH` não descrito é rejeitada. Quadros grandes mantêm a sondagem folha e a alocação única das revisões anteriores.

## 2. Auxiliares e epílogos

São descritas 22 auxiliares: verificação de arquivo regular; gravação e leitura completas; gravação e leitura posicionais; abertura de caminho verificado; abertura, fechamento, sincronização e bloqueio de recurso; gravação e leitura em recurso; publicação de arquivo; alocação e desalocação de lista; liberação, movimentação e acréscimo de descritor; impressão de inteiro; próximo byte do cache; leitura de inteiro e leitura de texto.

As auxiliares com quadro `RBP` preservam `RDI`/`RSI` antes de salvar `RBP`, mantêm a reserva fixa e retornam com `LEA RSP,[RBP]`, seguido dos `POP`s e `RET`. `MOV RSP,RBP` não é uma restauração reconhecida pelo analisador de epílogos Windows e deixou de ser emitido nesses retornos.

As primitivas de alocação, desalocação, fechamento e sincronização reservam 40 bytes desde a entrada e os devolvem somente no retorno comum. O cache de entrada também mantém a reserva desde o prólogo até o retorno, evitando reservas condicionais sem descrição. Impressão e leituras descrevem os registradores realmente empilhados e os respectivos tamanhos de quadro.

A pequena rotina de bloqueio Windows é uma folha auditada (`XOR EAX,EAX; RET`): a abertura exclusiva já é realizada por `CreateFileA`. Sua entrada de tabela descreve zero operações, sem inventar uma alocação.

A publicação valida prólogos, epílogos, limites, alinhamento, ordenação e ausência de sobreposição. Os ensaios corrompem instruções e metadados para comprovar que a verificação falha quando deve falhar. Linux conserva sua emissão anterior nas rotinas modificadas.

## 3. Ponteiro nulo de 64 bits

`escreve_literal`, `imprimir_inteiro` e a impressão de buffers passavam `lpOverlapped` a `WriteFile` com `MOV DWORD [RSP+32],0`. Essa instrução só zerava a metade inferior do ponteiro Windows de 64 bits. Dados anteriores no mesmo espaço podiam formar, por exemplo, o endereço inválido `0x200000000`.

O problema foi comprovado por depuração da violação de acesso dentro de `WriteFile` e reproduzido no diagnóstico de índice inválido em uma função e no copiador em blocos. As três emissões agora zeram a palavra completa com `MOV QWORD [RSP+32],0`. Os argumentos `DWORD` legítimos de `CreateFileA` continuam com sua largura própria.

Esse diagnóstico comprova a causa das violações observadas nesta revisão. Ele não comprova sozinho a causa da falha histórica de fechamento com `HIGH_ENTROPY_VA`; esse indicador permanece desativado.

## 4. O que os ensaios comprovam

`testes/test_desenrolamento_real_rs0415.py` extrai o código e os metadados do PE gerado. Um pequeno utilitário Python de testes registra a tabela em memória com `RtlAddFunctionTable`, confere a busca com `RtlLookupFunctionEntry` e chama `RtlVirtualUnwind`.

As pilhas artificiais são construídas pela interpretação independente das instruções emitidas, sem usar os códigos de desenrolamento para construir o resultado esperado. São exercitados os limites de cada instrução do prólogo, um ponto estritamente posterior ao prólogo, temporários no corpo e as etapas dos epílogos. A comparação inclui endereço de retorno, `RSP` e os oito registradores inteiros não voláteis. Os retornos e as exceções também conferem sentinelas em `XMM6`–`XMM15`. São cobertas `UWOP_ALLOC_SMALL` e ambas as formas de `UWOP_ALLOC_LARGE`.

Outro ensaio executa o prólogo real e injeta `INT3` no corpo de uma cópia do código. Um tratador vetorizado recebe o `CONTEXT` real da exceção. O teste percorre a rotina RS e seu chamador instrumentado com `RtlVirtualUnwind`, verifica o contexto recuperado e retoma o chamador. Isso exercita uma exceção real e as APIs Windows, mas não introduz `try`/`except`, SEH ou recuperação de exceções na linguagem RS.

Os retornos normais exercitam funções com quadros pequenos e grandes, incluindo 600000 bytes, e auxiliares de listas com sentinelas de registradores. Um ensaio adicional verifica diretamente a folha de sondagem e o contexto intermediário da chamada no prólogo, com ausência de tabela artificial. Outro envenena o espaço do quinto argumento e observa o ponteiro completo nas três emissões de impressão. O controle negativo adulterando um `UWOP_PUSH_NONVOL` precisa detectar restauração incorreta. Falhas nativas são falhas do teste; somente a indisponibilidade de Windows AMD64 permite ignorar esses ensaios.

Os exemplos finais exercitam 447 estados, 30 exceções `INT3` com 60 quadros percorridos, oito retornos normais, dois retornos diretos da sondagem e uma chamada intermediária dessa folha. O ensaio de impressão observa sete chamadas de `WriteFile` com ponteiro nulo completo depois de envenenar a pilha. Essas contagens representam casos de teste; não são uma medida de cobertura de todos os endereços do executável.

## 5. Diagnósticos de tipos locais de funções

O ensaio de impressão revelou que texto declarado somente em uma função podia gerar referência a `erro_texto_capacidade` sem emitir o respectivo bloco. A detecção de famílias de texto e listas fixas agora examina também os tipos locais de todas as funções. Os testes adicionais compilam os dois alvos e executam falhas de capacidade de texto e índice de lista nos níveis 0, 4 e 8, conferindo mensagem e status nativos.

## 6. Validação e limites

A execução local no Windows x64 concluiu 441 testes, sem falhas, com 13 ignorados por requisitos de plataforma ou permissões do ambiente. A revisão independente também confirmou que um ponteiro nulo truncado e uma corrupção de `XMM6` fazem os ensaios falhar.

Executar a suíte completa com `python -m unittest discover -s testes -v`. Os ensaios nativos novos são descobertos pelo mesmo comando no trabalho Windows do GitHub Actions; no Linux são explicitamente ignorados.

As referências de binários da 0.41.5 foram adicionadas separadamente das históricas. Elas voltam a incluir os exemplos de entrada e tipos que os testes antigos excluíam após alterações anteriores de E/S.

A cobertura não deve ser anunciada como desenrolamento universal de todo endereço do executável. Os blocos `erro_*` realinham a pilha com `AND` e encerram o processo; não são quadros retornáveis publicados pela tabela. A sondagem é folha, sem tabela artificial; a recuperação do seu retorno usa o comportamento de folha do Windows.

Os ensaios não constituem prova formal de segurança de memória, tratamento completo de exceções do sistema, Control Flow Guard ou autocompilação. O compilador de desenvolvimento continua em Python e os executáveis continuam nativos e independentes. `HIGH_ENTROPY_VA` continua desligado.

## Referências primárias

- [Convenção de chamadas x64](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention)
- [Prólogos e epílogos x64](https://learn.microsoft.com/en-us/cpp/build/prolog-and-epilog)
- [Informações de exceção x64](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64)
- [RtlAddFunctionTable](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtladdfunctiontable)
- [RtlLookupFunctionEntry](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtllookupfunctionentry)
- [RtlVirtualUnwind](https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtlvirtualunwind)
- [WriteFile e lpOverlapped](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)
