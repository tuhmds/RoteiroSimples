# Emprestimos somente para leitura de listas de registros (ELF64)

O emissor experimental escrito em RS agora reconhece parametros do tipo
`emprestimo[lista[NomeRegistro]]`, para tipos definidos antes das funcoes.
Nao copia os elementos, nao altera seu layout e nao transfere propriedade.
O compilador ainda depende do bootstrap Python para gerar o emissor RS.

## Exemplo

~~~rs
tipo Ponto {
    x: inteiro
    y: inteiro
}

funcao consultar(pontos: emprestimo[lista[Ponto]]) -> inteiro {
    retorne pontos[0].x + tamanho(pontos)
}

inicio {
    seja valores: lista[Ponto]
    seja p: Ponto
    p.x = 12
    adicione(valores, p)
    seja resposta = consultar(valores)
}
~~~

O resultado e 13.

## Modelo de memoria e de tipos

- O proprietario da lista de registros usa o tipo interno 20 + indice
  do registro e o descritor de tres qwords (ponteiro, tamanho, capacidade).
- O emprestimo usa o tipo interno 30 + indice do mesmo registro.
- Uma chamada aceita apenas identificador de lista proprietaria do mesmo
  esquema, ou outra referencia readonly desse mesmo esquema.
- A referencia aponta para o slot de ponteiro do descritor do proprietario.
  A leitura encontra o tamanho em [referencia - 8], e o ponteiro atual
  para os elementos em [referencia]. Isso e importante apos um mremap,
  pois o buffer pode mudar de endereco.
- Cada elemento ocupa N qwords e o indice linear e
  indice_elemento * N + indice_campo, com validacao de limites.
- Tamanho devolve a quantidade de registros, nunca a de bytes.
- A referencia pode ser repassada a outra funcao sem gerar uma copia,
  mas nao pode receber adicione ou escrita em um campo.
- A referencia nao libera o descritor (munmap pertence ao dono).
  Nao pode ser devolvida como valor inteiro.
- Erro 18: tipos incompatíveis, mutacao via emprestimo, argumentos
  temporarios ou coercoes invalidas. Erro 2: assinatura desconhecida.
  Acesso fora dos limites termina a aplicacao nativa com exit(23).

## Testes

~~~sh
python -m unittest testes.test_emprestimos_lista_registros_elf_rs -v
python -m unittest discover -s testes -v
~~~

A suite O0/O8 cobre lista vazia, reemprestimo, crescimento com mremap,
mistura de argumentos inteiros, escrita do proprietario depois da chamada,
tipos errados, tentativa de mutacao e indices invalidos.
Os jobs Windows validam o compilador RS, e o Linux executa o ELF gerado.

## Limites

Nesta fase os registros contem somente campos inteiro. Ainda faltam
emprestimos de registros isolados, registros aninhados, listas com
campos dinamicos, transferencia de ownership e a autocompilacao completa.
