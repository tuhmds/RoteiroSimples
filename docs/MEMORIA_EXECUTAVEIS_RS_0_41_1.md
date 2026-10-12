# RS 0.41.1 — Separação de memória e investigação da alta entropia

## Contexto

A RS 0.41 introduziu ELF64 PIE, NX para pilha e PE32+ com realocação DIR64, ASLR e NX. A versão 0.41.1 consolida o isolamento das mensagens constantes no Linux e documenta uma investigação reproduzível do comportamento com `HIGH_ENTROPY_VA` no Windows.

Os executáveis são montados diretamente pelo emissor RS: **não dependem de Python, C, LLVM ou biblioteca de execução externa**. O compilador permanece implementado em Python até que a própria RS alcance a autocompilação.

## Linux: separação real de código e dados

Anteriormente, uma única região `PT_LOAD` de leitura/execução incluía código e mensagens. Agora, quando há constantes, o ELF64 emite dois segmentos carregáveis:

- **Código:** `PT_LOAD`, `PF_R | PF_X`, sem escrita.
- **Constantes:** `PT_LOAD`, `PF_R`, sem escrita e sem execução.
- **Pilha:** `PT_GNU_STACK`, `PF_R | PF_W`, sem execução.

As constantes são colocadas após o alinhamento à página de 4096 bytes, sem misturar permissões na mesma página. As referências continuam relativas ao ponteiro de instrução (RIP), de modo que a base PIE pode ser aleatorizada pelo núcleo. Quando não há mensagens, o gerador não precisa criar uma região adicional.

### Testes de segurança e compatibilidade

`testes/test_protecoes_executaveis_rs041.py` passou a verificar:

- Cabeçalhos dos segmentos e suas permissões, inclusive ausência de segmentos graváveis e executáveis ao mesmo tempo.
- Alinhamento e localização das mensagens em região não executável.
- Resultado de programas com mensagens compilados em `-O 0` até `-O 8`.
- No Linux x86-64, inspeção de `/proc/<pid>/maps` em um processo real, confirmando mapeamentos separados `r-xp` e `r--p`.

O alinhamento de página aumenta o tamanho físico de alguns binários pequenos. Por isso, os testes de desempenho que antes comparavam somente o tamanho total do arquivo passaram a considerar a parte de **código realmente emitida**, desconsiderando preenchimento de alinhamento. Isso evita atribuir ao otimizador um aumento ou redução que pertence ao formato do executável. Os registros SHA-256 históricos foram preservados; novos registros representam os binários desta versão.

### Limites

Essa separação reduz a superfície de execução acidental de dados constantes, mas **não impede todos os ataques de corrupção de memória**. Não há garantia formal de integridade dos dados, verificação completa de referências, guardas de pilha próprias nem defesa integral contra corrupção de fluxo.

## Windows: investigação de HIGH_ENTROPY_VA

A RS conserva `DYNAMIC_BASE` e `NX_COMPAT` e a realocação nativa DIR64 efetiva. A opção adicional `HIGH_ENTROPY_VA` continua desativada.

Foi executado um diagnóstico temporário em CI com binários idênticos, modificando **somente** as características do PE entre `0x140` e `0x160`. Os programas simples com inteiros, textos, listas e uma função numérica executaram nos dois modos, nos cenários testados. Porém, um caso de abertura seguida de fechamento de arquivo terminou com exceção `0xC0000005` no modo de alta entropia.

Um depurador temporário capturou:

- A exceção ocorre no código do sistema, durante a sequência de fechamento de identificador.
- A instrução observada é uma escrita indireta por `RSI` (`mov qword ptr [rsi], 0x103`).
- O endereço apontado por `RSI` não estava acessível para escrita.
- O ponteiro da pilha (`RSP`) foi recuperado no contexto da exceção, permitindo distinguir o endereço inválido do ponteiro corrente da pilha.
- **Ambas** as configurações foram observadas carregando a imagem em endereços elevados e variados. Portanto, não podemos atribuir a falha apenas ao tamanho numérico do endereço base.

A investigação aponta para uma incompatibilidade que merece auditoria de ABI, valores de registradores preservados, estado da pilha e transição entre rotinas nativas e APIs Windows. A observação **não prova** que a corrupção ocorre exatamente na RS, nem que o sistema operacional seja defeituoso. Não foi introduzida correção especulativa.

O diagnóstico de exceção foi executado em testes temporários de desenvolvimento e **não fica incorporado à suíte distribuída**; seu resultado e os comandos necessários para repetição podem ser recuperados pelo histórico da ramificação de desenvolvimento.

## Metadados de desenrolamento de pilha (.pdata/.xdata)

Os arquivos PE ainda não oferecem metadados completos de desenrolamento para todos os quadros de função. Gerá-los corretamente exigirá padronizar os prólogos, alocações, salvamento de registradores e rotinas auxiliares.

**Não basta criar seções vazias ou ativar indicadores.** A próxima fase deverá definir uma descrição de prólogo/epílogo por função, assegurar compatibilidade com a ABI Windows x64 e então emitir estruturas `RUNTIME_FUNCTION` e `UNWIND_INFO` correspondentes, com testes de exceções e depuração.

## Situação de segurança

- **Validado:** ELF64 PIE; pilha não executável; código RX e constantes R; PE realocável com `DYNAMIC_BASE` e `NX_COMPAT`; execução nativa em Windows/Linux.
- **Não habilitado:** `HIGH_ENTROPY_VA` no PE; restauração de chamadas em falhas de exceção com metadados completos; Control Flow Guard; proteção de pilha própria por função.
- **Não prometido:** inviolabilidade de memória, ausência de vulnerabilidades ou aptidão para produção.

A linguagem segue experimental. Os componentes e novos identificadores controlados pelo projeto permanecem em português brasileiro, com sintaxe pública sem acentos.
