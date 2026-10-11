# Arquitetura, memória e otimizações — RS 0.6

A RS é experimental. Esta página distingue **implementado** de **proposto**.

## Implementado

- Gerador direto de instruções AMD64 e executáveis PE32+ (Windows) e ELF64 (Linux).
- Inteiros de 64 bits em slots fixos de 8 bytes na pilha. `deslocamento_variavel` centraliza os endereços.
- `leia(nome)`: chama `ReadFile` (Windows) ou `sys_read` (Linux), valida números assinados e não usa heap. Lê um byte por chamada ao SO, ainda sem buffer.
- Instruções primitivas `mov` compactas: `eax,imm32` (5 bytes), `rax,imm32` com sinal (7 bytes) e `movabs rax,imm64` (10 bytes). Preservam as flags.

## Prioridades técnicas

1. Criar IR tipada e separar análise, tipos, controle de fluxo e backend.
2. Formalizar overflow: atualmente soma, subtração e multiplicação não detectam estouro.
3. Ler stdin em blocos, com buffers de capacidade e limites verificados, e testar múltiplas leituras.
4. Remover o limite atual de seções PE de 4 KiB, corrigir layout/realocações, testar ABI e proteção de páginas.
5. Definir tempo de vida e propriedade dos dados; criar arrays/listas e textos com checagem de limites.
6. Manter testes diferenciais no Windows e Linux e introduzir benchmarks repetíveis.

## Ponteiros e memória (ainda não implementados)

- Referências seguras serão preferidas por padrão, com regras de mutação e duração.
- Textos e listas terão tamanho conhecido e verificação de limites.
- Ponteiros brutos somente em futuro módulo ou bloco explicitamente `inseguro`, especialmente para FFI, drivers e bibliotecas nativas.
- Heap: ainda escolheremos entre propriedade única, regiões, contagem de referências e outras estratégias, com base em casos concretos. Não há decisão sobre coletor de lixo.

## Plano de otimização

| Estágio | Proposta |
|---|---|
| O0 | Linha de base sem transformações semânticas |
| O1 | Codificação curta de constantes (implementada); depois propagação de constantes e instruções redundantes |
| O2 | Blocos básicos, registros e simplificação de desvios |
| O3 | Otimizações orientadas por benchmarks reais |

**Medições necessárias:** tempo de compilação, tempo de execução (múltiplas rodadas), tamanho dos binários e número de chamadas ao SO. Menos bytes não garante execução mais rápida. Não mover ou remover E/S, erros de divisão por zero nem verificações de overflow.

**Limites atuais:** não há IR tipada, decimais, leitura de texto, referências, ponteiros, heap, listas ou proteção completa de memória. Não utilizar para produção.
