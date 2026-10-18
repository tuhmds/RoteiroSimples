# RS-MEM — Pool tipado de blocos pequenos

Modulo público: `importe "padrao/pools.rts" como pools`.

## Implementado

O pool mantém um buffer contíguo prealocado com blocos de **16, 64 ou
256 bytes**, até 4096 blocos por instância. O estado de ocupação, as
versões (gerações) e a lista de índices disponíveis são armazenados
em coleções RS prealocadas. `alocar` utiliza espaço ainda não usado
ou reaproveita o último bloco liberado (LIFO). `liberar` zera todo
o bloco antes de disponibilizá-lo novamente.

Cada identificador contém índice e versão; versões são incrementadas
por alocação. Isso detecta uso após liberação, liberação dupla
e identificadores anteriores após reuso. Ao alcançar o teto de
geração, recusa a alocação em vez de produzir wraparound.

## Semântica e limites

- `criar(classe, quantidade)` retorna `resultado[Pool]`.
- Mutações `alocar(pool)`, `escrever(pool, id, offset, byte)` e
  `liberar(pool, id)` consomem e devolvem a propriedade do pool.
- Os últimos índices/gerações ficam em `ultimo(empreste(pool))`;
  código 4 indica capacidade esgotada.
- `ler` devolve `resultado[inteiro]` para detectar identificador
  inativo ou inválido (3) e deslocamento fora do bloco (6).
- `escrever` reporta erros pelo `codigo_erro` do pool.
- Há validação do valor entre 0 e 255, e os dados liberados são zerados.

Isto é um **pool em RS**, não um alocador global nativo transparente,
não tem concorrência nem suporte a `malloc`/ponteiros externos.
Metadados são campos públicos, pois a linguagem ainda não dispõe de
encapsulamento de estruturas opacas; não se deve modificá-los fora da
biblioteca. Não representa uma prova de segurança para código que
altere diretamente esses campos. É uma implementação funcional para
uso voluntário e base de comparação com pools no emissor nativo.

Depende do `reserve_capacidade` do PR #31. A ABI nativa não foi
alterada. Não introduz overcommit automático, compactação, NUMA
nem integração de LLMs. Não há novas dependências de execução.

## Regressão

`python -m unittest testes.test_rs_mem_pool -v`

Testes executam o binário RS no alvo nativo em O0, O4 e O8,
incluindo reuso, anti-ABA, slots cheios, liberação dupla,
zeragem, leitura inválida e as três classes. A CI completa
Windows/Linux é obrigatória para integração.
