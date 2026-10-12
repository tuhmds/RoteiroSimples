# RoteiroSimples: memoria, ponteiros e otimizacao

Documento de engenharia para a RS 0.8. **Projetos e propostas nao sao funcionalidades prontas.**

## Situacao atual (implementado)

- Arquivos `.rts` sao analisados em Python apenas durante a compilacao. Os programas gerados executam codigo de maquina x86-64 diretamente, como ELF64/Linux ou PE32+/Windows.
- Na RS 0.8, as instrucoes aritmeticas add/sub/imul/neg usam a flag de overflow OF e salto JO; situacoes invalidas param com codigo 1. A IR tipada (ir.py) e uma arvore intermediaria de nos imutaveis, nao CFG nem SSA.
- Variaveis de inteiro de 64 bits ocupam 8 bytes em posicoes fixas na pilha. A funcao `deslocamento_variavel` centraliza o calculo do endereco.
- Operacoes matematicas usam registradores `RAX`, `RCX`, `RDX` e `R10`. Comparacoes usam as flags da CPU e instrucoes `setcc`; repeticoes usam saltos relativos.
- No Windows, chamadas a `ReadFile` e `WriteFile` usam a ABI x64 da Microsoft e suas areas de pilha. No Linux, usamos `syscall` diretamente.
- Na RS 0.8, a rotina nativa de `leia` valida o sinal, digitos, espacos, fim de linha, EOF e limites do inteiro. Nao aloca memoria no heap: le um byte por chamada do SO usando um pequeno espaco temporario na pilha.
- A carga de constantes usa a menor forma de `mov` que preserva valor e flags: `mov eax, imm32` (5 bytes), `mov rax, imm32` com extensao de sinal (7 bytes) ou `movabs rax, imm64` (10 bytes).

## Problemas reais a resolver antes de sistemas profissionais

1. **Entrada de dados:** a leitura byte a byte faz chamadas demais ao SO. Implantar buffer fixo com tamanho e limites verificados, primeiro 4 KiB e depois entrada em blocos, observando leitura de varias linhas.
2. **Protecao dos inteiros:** concluido parcialmente na RS 0.8: soma, subtracao, multiplicacao e negacao com erro (OF/JO). Faltam definicoes para futuros tipos e operacoes.
3. **Formato PE:** o backend ainda usa tres secoes pequenas e layout limitado a 4 KiB; precisamos calcular tamanhos dinamicamente, alinhamento e realocacoes.
4. **Layout de memoria:** separar dados constantes, dados mutaveis, pilha e heap. Validar alinhamento e convencoes de chamada em cada plataforma; ampliar os testes de ABI.
5. **Erros/diagnosticos:** Windows escreve erros de execucao na saida padrao, Linux na saida de erro; padronizar, oferecer linha da origem e codigos de erro definidos.
6. **Seguranca do compilador:** o gerador ainda nao foi auditado para entradas hostis. Compilacao e programas executados nao devem ser considerados seguros para producao.

## Modelo proposto de memoria (ainda nao implementado)

- **Valores:** `inteiro`, `real`, `logico` e tipos compostos com tamanho e alinhamento definidos formalmente.
- **Referencias seguras:** acesso por referencia com verificacao de vida util e emprestimo exclusivo para alteracao, sem permitir referencia pendurada. Definir se sera feito por analise estatica ou por verificacoes em execucao.
- **Listas e textos:** armazenamento com tamanho e capacidade rastreados; acesso com limite verificado; responsabilidade de desalocacao explicita na implementacao.
- **Heap:** estudar estrategia por regiao, propriedade unica e contagem de referencias para objetos compartilhados; decidir com casos reais de uso, nao apenas por preferencia.
- **Ponteiros brutos:** somente numa futura interface de baixo nivel `inseguro`, para drivers, interoperabilidade C e FFI. O usuario iniciante nao precisara deles para aplicativos e jogos.

**Decisao por enquanto:** nao expor enderecos de memoria ou aritmetica de ponteiros ao programa RS antes de existir sistema de tipos, regras de tempo de vida e testes de acesso fora dos limites.

## Plano de otimizacao

| Etapa | Medida | Validacao |
|---|---|---|
| O0 | Baseline sem transformacoes de programa, com geracao direta de codigo | testes de semantica e bytes gerados |
| O1 | Codificacao curta de constantes (feita na RS 0.8) e eliminacao de instrucoes redundantes | mesmo resultado em Windows e Linux, reducao de bytes |
| O2 | CFG, propagacao interblocos e eliminacao de redundancias, respeitando overflow e erros | testes diferenciais O0/O2 |
| O3 | Alocacao de registradores, menos `push`/`pop`, melhoria de chamadas e inlining controlado | benchmarks repetiveis em jogos, calculos e I/O |
| Multiplataforma | Backends separados por arquitetura (x86-64, ARM64), com IR comum | matrizes em hardware correspondente |

Nao ativar otimizacoes de divisao por zero, overflow ou reordenacao de efeitos de I/O que alterem o comportamento observavel do programa. A IR tipada inicial existe na RS 0.8 (arvores de instrucoes e expressoes). Ainda precisamos de CFG, blocos basicos explicitos e convencoes de chamada especificadas para otimizacoes maiores.

## Como medir

- Capturar tempo de compilacao, tempo de execucao mediano de multiplas rodadas, tamanho de executavel e chamadas ao SO.
- Usar programas representativos: soma de muitos inteiros, lacos aninhados, processamento de entradas, listas, estruturas e carga de arquivos (conforme implementados).
- Comparar mesma maquina, sistema, compilador e entrada; repetir medidas para evitar ruido.
- Os numeros de velocidade nao foram medidos nesta etapa; tamanho menor **nao significa automaticamente** programa mais rapido.
