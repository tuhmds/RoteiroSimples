# Listas dinamicas de inteiros no emissor ELF64 escrito em RS

O modulo emissao_listas_elf.rts agora emite lista[inteiro]
**dinamica** para Linux x86-64. O emissor e escrito em RS,
mas ainda e construido pelo bootstrap Python do desenvolvimento.
Nao significa autocompilacao completa.

## Exemplo

~~~rs
funcao contar() -> inteiro {
    seja valores: lista[inteiro]
    adicione(valores, 11)
    adicione(valores, -3)
    valores[0] = valores[0] + 7
    retorne valores[0] + valores[1] + tamanho(valores)
}
inicio {
    seja resultado = contar()
}
~~~

O resultado e 17. Uma lista nasce vazia, adicione insere ao final,
tamanho conta **elementos** (nao bytes), e indexacao le/atualiza
um inteiro signed64.

## Descritor e propriedade

O tipo interno **5** da IR utiliza 3 slots de 8 bytes na pilha:
**ponteiro**, **numero de elementos**, **capacidade em bytes**.
Reutiliza o descritor dos buffers dinamicos de bytes.

Na declaracao, mmap (syscall 9) aloca 64 bytes: oito inteiros signed64,
com comprimento logico zero. Ao completar a reserva, mremap
(syscall 25 com MREMAP_MAYMOVE) duplica sua capacidade para 16, 32,
64, 128 e assim por diante. O ponteiro atualizado fica no descritor.
Ele pode mudar apos mremap, portanto os indices nao guardam enderecos
anteriores dos elementos.

O teto deste estagio e **1 MiB por lista** (131072 elementos).
A 131073a adicao encerra com exit(24). Falhas de mmap e mremap
tambem encerram com exit(24).

## Seguranca e limpeza

- Indices negativos, indices >= tamanho logico e escrita fora do
  comprimento terminam com exit(23), antes de acessar memoria.
- Elementos nao inicializados, alem do comprimento logico,
  nao podem ser acessados mesmo com capacidade disponivel.
- A propriedade da memoria pertence ao escopo da declaracao.
  munmap e emitido automaticamente em retorno, fechamento de
  bloco e funcao, pare e continue, preservando retorno e saida.
- Emprestimo de listas, passagem de listas entre funcoes,
  transferencia de propriedade, listas de registros e devolucao
  de listas por funcao ainda estao fora deste subconjunto.
- A declaracao aceita lista[inteiro] sem inicializador. Lista de
  outro tipo ou inicializador: diagnostico 2; coercao da lista
  para inteiro ou atribuicao integral: diagnostico 18.

## Validacao

~~~sh
python -m unittest testes.test_listas_locais_elf_rs -v
python -m unittest discover -s testes -v
~~~

A suite O0/O8 cobre 9, 17, 65, 1000 e 4097 elementos, valores
signed64, acessos e escritas depois do remapeamento, limite de 1 MiB,
limpeza automatica de memoria em lacos e casos invalidos.

Os executaveis ELF64 gerados rodam em Linux x86-64. O Windows compila
o emissor escrito em RS, mas nao executa o ELF.

## Proximos marcos

1. Emprestimo read-only de lista[inteiro] entre funcoes.
2. Listas de registros com layout e movimentacao segura.
3. Compilar as estruturas do lexer e parser escritos em RS
   com o emissor RS em um bootstrap de duas geracoes.
