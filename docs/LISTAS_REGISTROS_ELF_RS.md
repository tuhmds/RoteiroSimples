# Listas de registros inteiros no emissor ELF64 escrito em RS

Este modulo expande os registros locais: agora a RS pode declarar
lista[NomeDoRegistro], inserir valores por copia e acessar campos
de elementos dinamicamente alocados. O emissor continua experimental,
com bootstrap Python para construir o compilador escrito em RS.

## Exemplo

~~~rs
tipo Ponto {
    x: inteiro
    y: inteiro
}
funcao calcular() -> inteiro {
    seja pontos: lista[Ponto]
    seja p: Ponto
    p.x = 10
    p.y = 20
    adicione(pontos, p)
    p.x = 50
    pontos[0].y = 2
    retorne pontos[0].x + pontos[0].y
}
inicio {
    seja resultado = calcular()
}
~~~

Resultado: 12. A insercao copia os campos do registro local,
portanto alteracoes posteriores em p nao modificam o elemento.
A escrita em pontos[indice].campo altera somente a lista.

## Modelo de memoria

- Registro: 1 a 8 campos inteiro signed64, cada um com 8 bytes.
- A lista usa layout AoS (array de estruturas): os campos dos
  elementos sao contiguos, preservando ordem e tamanho estatico.
- O descritor local de 3 qwords possui ponteiro, numero de
  elementos e capacidade em bytes.
- mmap aloca inicialmente 64 bytes, mremap(MREMAP_MAYMOVE)
  duplica a reserva conforme a necessidade. Nao ha enderecos de
  elementos mantidos entre operacoes de crescimento.
- O limite inicial de reserva e 1 MiB por lista. Expansao
  acima de 1 MiB ou falha na alocacao gera exit(24).
- Indice negativo ou >= tamanho logico causa exit(23) antes de
  ler ou escrever. Uma leitura de campo nao atravessa o proximo
  elemento, pois o stride e o numero de campos do esquema.
- A limpeza automatica usa munmap do proprio descritor, em
  escopos, retorno antecipado e desvios de lacos.

## Restricoes

- Somente listas de registros de campos inteiros.
- Insercao somente de variavel local proprietaria com o mesmo
  tipo; nao aceita literais temporarios nem registros aninhados.
- Ainda nao e possivel passar listas de registros por parametro
  ou devolver registros e listas por valor.
- Registros ja existentes podem ser atualizados campo a campo,
  nao por atribuicao do elemento inteiro.
- Os tipos existentes lista[inteiro], emprestimo[lista[inteiro]],
  bytes dinamico e registro local mantem seus contratos.

## Testes

~~~sh
python -m unittest testes.test_listas_registros_elf_rs -v
python -m unittest discover -s testes -v
~~~

A matriz O0/O8 inclui crescimento de mais de 100 elementos,
escritas apos realocacao, copia independente da fonte, campos
multiplos, indices invalidos e esquemas incompatíveis.
Linux executa o ELF64; Windows recompila e valida o emissor RS.

## Proximas etapas

Acrescentar emprestimo readonly de lista[Registro], registros
aninhados e valores estruturados em parametros e retornos.
Esses passos permitirao representar as estruturas de tokens
do lexer da RS, ainda sem prometer autocompilacao completa.
