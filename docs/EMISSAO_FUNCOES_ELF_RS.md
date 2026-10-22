# Emissao ELF de funcoes e parametros inteiros em RS

O modulo `padrao/emissao_funcoes_elf.rts` e a ferramenta
`exemplos/ferramentas/compilador_funcoes_elf_rs.rts` acrescentam
`call rel32`, `ret`, parametros e retorno inteiro a cadeia incremental
de binarios Linux ELF64 escrita na propria RoteiroSimples.

## Contrato inicial

Um ou mais blocos `funcao` **antes** de `inicio`. No maximo 16 funcoes,
com ate quatro parametros `inteiro` cada, retorno `inteiro`. O corpo
contem somente `retorne` seguido de uma expressao aritmetica, sem
chamadas, laços ou variaveis locais. Parametros nao podem repetir nomes.

```text
funcao multiplicar(a: inteiro, b: inteiro) -> inteiro {
    retorne a * b
}

funcao acrescer(valor: inteiro) -> inteiro {
    retorne valor + 3
}

inicio {
    seja base = 5
    seja produto = multiplicar(base + 1, 4)
    seja final = acrescer(produto)
}
```

No bloco principal, cada instrucao e uma declaracao `seja nome = ...`:
o lado direito aceita expressao aritmetica ou **uma chamada direta**
de funcao cujo argumento seja uma expressao aritmetica. Nao aceita
`multiplicar(1,2)+3`, chamadas aninhadas, atribuicoes separadas,
`se`, `enquanto` ou `senao` nesse novo emissor.
O valor da ultima declaracao e usado como status de saida Linux
(menos os bits superiores: observam-se somente os oito bits inferiores).
A ferramenta gravara `resultado_funcoes_elf` quando a fonte for valida.

## Emissao

- `_start` inicia o programa e reserva um slot para cada declaracao.
- Argumentos sao avaliados da direita para a esquerda e colocados
  na pilha. A chamada usa `E8 rel32`, cujo destino e corrigido depois.
- Cada funcao possui seu proprio quadro em `rbp`. Parametros entram
  de `[rbp+16+8*i]` e vao para locais em `[rbp-8*(i+1)]`.
- O resultado de `retorne` vai para `rax`; o epilogo usa `leave; ret`.
- A chamada no bloco principal limpa os argumentos e guarda `rax`
  no slot da declaracao.
- A imagem ELF e construida em RS; o Python atual apenas
  **constroi a ferramenta nativa**, e nao emite o arquivo final.

Esta convenção de chamada e **privada**, apenas para funcoes que este
proprio emissor produz. Nao implementa ainda o System V ABI, acesso a
bibliotecas, compilacao geral de programas RS, recursao ou bootstrap.
O modulo compartilha emissao aritmetica e remendo de saltos com
`padrao/emissao_fluxo_elf.rts`, sem alterar o comportamento desse emissor.

## Testes

```text
python -m unittest testes.test_emissao_funcoes_elf_rs -v
```

A CI compila a ferramenta escrita em RS para Windows/Linux (O0 e O8),
inspeciona a estrutura ELF e executa o arquivo produzido no Linux
comparando codigos de saida com contas independentes. Casos de uso
fora do subconjunto nao devem gerar arquivo de saida.

## Proxima etapa

Integrar chamadas ao emissor de `se`/`enquanto`, incorporar uma
arvore de instrucoes completa e adicionar variaveis/retornos mais
complexos nas funcoes, com ligacao de simbolos e ABI adequada.
