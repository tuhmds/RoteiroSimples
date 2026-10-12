# Entrada bufferizada e efeitos da IR — RS 0.19

## Implementado

O runtime x86-64 mantém **um único cache de entrada de 1.024 bytes** na pilha do
programa, com dois índices de 64 bits: bytes disponíveis e posição de leitura.
A rotina `entrada_proximo_byte` devolve 1 + byte, 0 (EOF) ou -1 (falha de E/S).
No Linux usa `read` e, no Windows, `ReadFile`. `leia(inteiro)`,
`leia(lista[indice])` e `leia(texto)` compartilham esse estado e preservam
os bytes adiantados pela chamada ao sistema operacional. O cache é ativado
apenas em programas que usam leitura.

O tamanho conservador de 1.024 bytes, somado ao teto atual de 256 slots locais,
mantém a reserva principal de pilha abaixo de uma página de 4 KiB na versão
Windows, que ainda não oferece sondagem de páginas de pilha. Este não é um
substituto para uma implementação geral de stack probing.

**Comportamentos preservados:** fim de linha LF ou CRLF; EOF após número;
espaços e sinal dos inteiros; limites de 64 bits; validação UTF-8; capacidade
dos textos; índice verificado nas listas; falhas com código de saída 1.
Texto em buffer vazio no EOF permanece válido. As leituras podem vir de console
interativo, pipe ou redirecionamento de stdin.

## Efeitos observáveis na IR

`compilador/efeitos.py` classifica cada instrução e suas expressões quanto a:

- `leituras`: conjuntos conservadores de símbolos acessados;
- `escritas`: conjuntos de símbolos alterados;
- `entrada` e `saida`: operações de stdin/stdout;
- `pode_falhar`: índice inválido, aritmética verificada, entrada ou capacidade.

A análise percorre `se`, `enquanto` e `para`, sem confundir efeitos de uma
instrução com os de todo seu bloco. Use `--mostrar-efeitos` ou
`--salvar-efeitos efeitos.json`. A saída é um diagnóstico para preparar a
modelagem posterior de memória no SSA; **não é ainda Memory SSA, alias analysis
ou uma permissão para reordenar/remover operações de memória**.

Programas com listas ou textos continuam usando o backend seguro de pilha
mesmo em `-O 6`. Os otimizadores dos níveis anteriores permanecem inalterados.

## Medição de exemplo (Linux, pipe)

Em oito execuções medidas após uma de aquecimento, foram lidos 30.000 números
`2` seguidos de LF. Na máquina do desenvolvimento, as medianas foram **8,19 ms
(RS 0.18)** e **0,51 ms (RS 0.19)**, aproximadamente 16 vezes mais rápido
neste microbenchmark. Os executáveis ELF respectivos mediram 1.206 e
1.335 bytes. Use `python benchmarks/entrada_bufferizada.py --comparar-com
CAMINHO_DA_RS_0_18` para repetir no seu ambiente. Nenhuma garantia de
velocidade é feita para outros programas, discos, terminais ou plataformas.

## Próximas etapas

- Representar regiões de memória e efeitos ordenados nos blocos CFG e SSA.
- Definir regras de aliasing e empréstimos antes de permitir referências.
- Implementar I/O de saída com escrita parcial correta e tratamento de falhas.
- Evoluir a pilha com sondagem de páginas antes de admitir quadros maiores.
