# RS 0.41 — Segurança do carregamento nativo ELF e PE

## Objetivo

Aprimorar a proteção de carregamento dos executáveis gerados diretamente pela RoteiroSimples. A implementação usa somente o próprio emissor de máquina e os formatos nativos, sem depender de C, LLVM, compilador externo ou ambiente de execução Python.

**A RS continua experimental, e não deve ser considerada pronta para produção.** As proteções descritas dizem respeito principalmente a endereçamento e permissões de memória, não a segurança completa do programa.

## Linux x86-64

O gerador em `backend/linux_elf.py` agora emite:

- ELF64 `ET_DYN` (tipo 3), com entrada relativa à imagem, permitindo carregamento com endereços aleatórios de acordo com a política do núcleo;
- segmento `PT_LOAD` de leitura e execução, sem permissão de escrita;
- cabeçalho `PT_GNU_STACK` de leitura e escrita, **sem permissão de execução**;
- executável independente de interpretador dinâmico: não depende de `PT_INTERP`, libc, Python nem LLVM na execução.

A estrutura do gerador utiliza referências internas e de dados relativas ao ponteiro de instrução (RIP). Por isso, não precisa resolver endereços absolutos de funções e mensagens com um vinculador externo quando a imagem muda de endereço.

Há teste estrutural de cabeçalhos e um teste de execução real que, no Linux x86-64 com ASLR do núcleo ativo, observa endereços de carregamento diferentes de processos separados em `/proc/<pid>/maps`. O teste também confere a ausência de execução na região de pilha reportada.

**Limites:** as mensagens constantes e o código atualmente compartilham o único segmento carregável de leitura e execução. Portanto, ainda não separamos completamente memória executável e dados somente de leitura. O PIE depende da política ASLR do núcleo e do ambiente. Não há proteção contra todas as corrupções de memória, verificadores de pilha, sanitizadores, mecanismos de controle de fluxo ou prova formal de ausência de bugs.

## Windows x64

O gerador em `backend/windows_pe.py` agora emite PE32+ com:

- quatro seções: `.text`, `.idata`, `.rdata` e `.reloc`;
- entrada por um salto nativo real `MOVABS RAX, endereço; JMP RAX`, cujo endereço absoluto de 64 bits é ajustável no carregamento;
- uma realocação `IMAGE_REL_BASED_DIR64` **aplicada ao endereço efetivamente utilizado pelo ponto de entrada** — não apenas um registro de preenchimento;
- `IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE` para permitir ASLR;
- `IMAGE_DLLCHARACTERISTICS_NX_COMPAT` para compatibilidade com execução não permitida onde o sistema oferece essa proteção;
- tamanho do cabeçalho, diretório de realocações, endereços relativos e alinhamento das seções calculados de acordo com a estrutura final da imagem.

O teste estrutural confere a tabela DIR64, o destino real do salto, os atributos das seções e as opções de proteção. Os testes nativos em Windows executam aplicações reais, inclusive com recursos de arquivo, funções e dados compostos.

**Alta entropia de endereços (HIGH_ENTROPY_VA): não está habilitada.** Durante o desenvolvimento, essa opção provocou violações de acesso em alguns programas que funcionavam com `DYNAMIC_BASE`. Uma verificação separada confirmou que `DYNAMIC_BASE` com `NX_COMPAT`, sem a opção adicional de alta entropia, preserva a compatibilidade nesses casos. Não anunciaremos suporte a alta entropia até diagnosticar e corrigir as suposições antigas de endereçamento/ABI que impedem sua ativação.

**Limites:** a geração PE ainda não oferece tabelas completas de informações de desenrolamento de exceções (`.pdata`/`.xdata`), Control Flow Guard ou proteção própria contra esmagamento de pilha. O cabeçalho ASLR solicita a política ao Windows; os testes atuais não comprovam que todos os ambientes Windows sorteiem bases distintas em todos os lançamentos. A imagem não deve ser divulgada como endurecida integralmente.

## Compatibilidade, testes e registros históricos

A RS 0.41 manteve os níveis `-O 0` a `-O 8` e os comandos públicos existentes; as mudanças estão nos formatos nativos dos arquivos finais.

Como os cabeçalhos e seções agora são diferentes, os valores SHA-256 dos arquivos executáveis mudam legitimamente, mesmo quando o programa conserva o mesmo comportamento. Os registros originais RS 0.8 e RS 0.11 foram mantidos, e novos registros de comparação foram introduzidos em `testes/fixtures/rs041_binarios_08.json` e `rs041_binarios_11.json`.

O arquivo `testes/test_protecoes_executaveis_rs041.py` verifica estrutura ELF/PE, permissões, realocação verdadeira, invariantes dos cabeçalhos e execução real em diferentes níveis de otimização. A suíte anterior também é executada inteiramente em Linux e Windows para detectar regressões de arquivos, funções, registros e SSA.

Nenhuma dependência obrigatória de execução foi acrescentada. O compilador de desenvolvimento permanece em Python, e a autocompilação em RS ainda é uma meta futura.

## Próximas prioridades

1. Investigar em detalhe a incompatibilidade do backend nativo com HIGH_ENTROPY_VA no Windows, sem ativar a opção prematuramente.
2. Acrescentar metadados de desenrolamento de pilha e proteções de fluxo de controle quando tecnicamente justificadas.
3. Separar segmentos de código e dados de leitura no ELF, mantendo permissões mínimas.
4. Auditar alocação de pilha, tratamento de endereços e passagem de parâmetros nativos com casos de funções/recursos.
5. Desenvolver testes de carregamento aleatório e deslocamento de imagem mais amplos, sem depender de ferramentas externas como parte obrigatória da linguagem.

A segurança deve ser comprovada por testes e semântica, não por uma opção ativada artificialmente no cabeçalho.
