# Primeira lista de inteiros no emissor ELF64 escrito em RS

Este incremento permite representar `lista[inteiro]` **local** no
subconjunto ELF64 experimental da RS. E uma etapa deliberadamente limitada
de autocompilacao: o backend de desenvolvimento em Python ainda constroi
o emissor escrito em RS. O proprio emissor gera os programas ELF64
testados sem usar estruturas de lista do runtime Python.

## Uso

```rs
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
```

O resultado e 17; a lista comeca vazia. `adicione` insere ao final,
`tamanho` retorna o numero de elementos e o acesso `valores[indice]`
le ou atualiza um inteiro signed64.

## Contrato de memoria

- Tipo interno **5** na IR; alocacao local de **9 slots de 8 bytes**
  (comprimento e oito elementos) no frame ELF64 x86-64.
- Capacidade fixa **8** nesta etapa. A lista dinamica do compilador
  convencional nao tem esse mesmo limite, portanto isto **nao e**
  implementacao completa de `lista[inteiro]`.
- O primeiro slot e inicializado com comprimento zero; elementos
  nao inicializados nunca sao acessiveis por indices validos.
- Acesso com indice negativo ou >= `tamanho`, ou adicao do nono
  elemento, encerra deterministicamente o executavel com `exit(23)`.
- Nenhum ponteiro da lista local escapa para fora do quadro.
  Passagem de listas a funcoes, devolucao de listas, `mova`,
  `emprestimo[lista]`, listas de registros e expansao da
  capacidade nao estao disponiveis neste emissor.
- Declaracao `seja valores: lista[inteiro]` e valida sem inicializador.
  Um inicializador com `=` ou elemento de outro tipo recebe
  diagnostico 2; usar uma lista como inteiro recebe 18.
- A emissao ocorre no Linux ELF64 x86-64; os jobs Windows validam a
  ferramenta de compilacao escrita em RS, mas nao executam o ELF gerado.

## Testes

`python -m unittest testes.test_listas_locais_elf_rs -v`

A suite exercita O0/O8, tamanho inicial, adicao, escrita e leitura,
multiplicacao e sinais negativos, escopos, 8 elementos, rejeicao da
nona adicao e de indices invalidos, tipagem e chamadas inteiras.

## Proximos marcos

O passo natural e substituir a capacidade fixa por uma representacao
dinamica gerenciada, adicionar `emprestimo[lista[inteiro]]` read-only,
seguido por listas de registros e transferencia de propriedade.
So depois sera possivel tentar compilar estruturas como a lista de
unidades lexicas do proprio compilador RS.
