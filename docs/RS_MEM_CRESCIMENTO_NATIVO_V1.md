# RS-MEM — Crescimento nativo de memória, primeira implementação

Base: RS 0.42U, alteração experimental sem ampliar a sintaxe.

## Diagnóstico confirmado

Antes desta entrega, `rs_valor_reservar` sempre solicitava novo mapeamento
e copiava os bytes utilizados quando a capacidade aumentava. Isso funcionava,
mas podia copiar repetidamente coleções extensas. As coleções, bytes e textos
compartilham um descritor nativo de três palavras: ponteiro, comprimento e
capacidade. Não foi introduzida nenhuma representação concorrente.

## Mudança implementada

No Linux x86-64, após validar a nova capacidade e os tamanhos, o emissor
tenta `mremap` (syscall 25, `MREMAP_MAYMOVE`) quando já existe uma região.
Se obtiver sucesso, armazena o endereço retornado, que pode ser diferente
do endereço antigo, e atualiza a capacidade. O núcleo preserva o conteúdo
existente do mapeamento. Se a syscall falhar, o caminho antigo aloca outro
mapeamento, copia os bytes efetivamente usados e libera a região antiga.

O primeiro armazenamento continua sendo obtido por `mmap`. No Windows,
`VirtualAlloc`/`VirtualFree`, os metadados de desenrolamento e a ABI
existente permanecem inalterados. Os descritores e as regras de propriedade
e empréstimo também não mudaram.

Esta mudança **não** é um alocador de arenas, pool de blocos, coletor de lixo,
compactador, sistema de memória NUMA ou garantia de ganho de desempenho.

## Garantias a validar

- Equivalência de resultados de listas/bytes/textos em O0, O4 e O8;
- integridade de dados quando o núcleo move fisicamente o mapeamento virtual;
- fallback por erro de `mremap`, sobretudo falhas transitórias;
- invariantes de tamanho, capacidade, descarte e índice;
- ausência de impacto em Windows e metadados de desenrolamento;
- desempenho medido, inclusive casos em que `mremap` é mais lento.

Testes automatizados: `testes/test_rs_mem_crescimento.py` e toda a suíte
preexistente. Um ensaio substitui a syscall `mremap` por um número inválido
no executável de teste: o núcleo retorna `ENOSYS` e a reserva, cópia e
liberação anterior precisa preservar os dados. Isso não substitui uma
campanha completa de pressão de memória e falhas.

Benchmark: `benchmarks/realocacao_rs_mem.rts`. Executar com
`python -m benchmarks.medir --fonte benchmarks/realocacao_rs_mem.rts --repeticoes 17 --json realocacao.json`.
Comparar os resultados com a `main` anterior antes de afirmar ganho.

## Próximas etapas condicionadas aos resultados

1. Medir custos de alocação e realocação, picos de RAM, falhas e latência.
2. Projetar pools/arenas com sincronização, contabilidade e liberação
   correta; preservar o ABI de três palavras.
3. Expandir análise de escape e alias na IR/Memory SSA antes de otimizar
   valores proprietários em funções complexas.
4. Só então investigar memória por níveis, compressão e usos para LLMs,
   preferencialmente como módulos opcionais.

Não introduzir opções O9 fictícias, alterações silenciosas de semântica,
novas dependências de runtime ou promessas de segurança geral.
