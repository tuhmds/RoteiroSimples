# Emprestimos somente para leitura de listas no ELF64 escrito em RS

Este incremento permite aceitar parametros do tipo
emprestimo[lista[inteiro]] no subconjunto experimental ELF64 x86-64.
O ponteiro passado aponta para o descritor do proprietario, nao
para uma copia dos elementos.

## Exemplo

~~~rs
funcao somar(primeiro: inteiro, itens: emprestimo[lista[inteiro]]) -> inteiro {
    retorne primeiro + itens[0] + tamanho(itens)
}
inicio {
    seja valores: lista[inteiro]
    adicione(valores, 12)
    seja resultado = somar(3, valores)
}
~~~

A consulta resulta em 16. O emprestimo so dura durante a chamada.
A funcao chamada pode consultar elementos e tamanho e repassar o
emprestimo a outra funcao que tambem exija referencia readonly.

## Contrato de memoria

- O tipo interno 5 representa a lista dinamica proprietaria.
- O tipo interno 6 representa a referencia readonly na funcao chamada.
- O descritor do dono possui ponteiro, comprimento em elementos e
  capacidade em bytes. A referencia aponta para o primeiro campo.
- O compilador le o comprimento em [referencia - 8] e o ponteiro
  real em [referencia]. Para acessar elemento, consulta o descritor,
  verifica indices negativos ou fora do tamanho, depois le o valor.
- A funcao chamada nao executa munmap, nao assume propriedade e
  nao retorna a referencia ao chamador como valor.
- As operacoes de escrita por indice, insercao ou transferencia de
  propriedade a partir da referencia sao proibidas, erro 18.
- Chamada aceita apenas identificador de lista proprietaria ou
  de referencia valida; um temporario nao pode ser emprestado.
- O dono conserva seu contrato de liberar a lista ao sair do escopo.
- O emissor atual continua sem tipos de registros, listas de registros,
  emprestimos mutaveis ou autocompilacao completa.

## Testes

~~~sh
python -m unittest testes.test_emprestimos_lista_inteiros_elf_rs -v
python -m unittest discover -s testes -v
~~~

Os casos exercitam O0 e O8, listas vazias, listas redimensionadas por
mremap, mistura de parametros, reemprestimo entre duas funcoes,
escrita do proprietario apos emprestimo e rejeicoes de memoria e
tipagem. O ELF gerado e executado em Linux x86-64; Windows verifica
o compilador escrito em RS pelo bootstrap de desenvolvimento.
