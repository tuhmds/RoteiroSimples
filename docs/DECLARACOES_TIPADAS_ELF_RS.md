# Declaracoes locais tipadas no emissor ELF da RS

O analisador de instrucoes `biblioteca_padrao/instrucoes_integradas_elf.rts`,
escrito em RoteiroSimples, reconhece duas formas de declaracao de
inteiros no subconjunto experimental ELF64:

```rs
funcao somar(a: inteiro, b: inteiro) -> inteiro {
    seja resultado: inteiro = a + b
    retorne resultado
}

inicio {
    seja valor: inteiro = somar(2, 3)
}
```

A forma anterior, `seja valor = expressao`, continua valida e usa o
mesmo caminho de emissao de maquina.

## Contrato atual

- O tipo explicito aceito e **`inteiro`** (inteiro com sinal de 64 bits).
- Pode ser usado em `inicio`, funcoes, `se`, `senao` e `enquanto`.
- O resultado da expressao inicializadora continua produzido pelo
  emissor atual, podendo incluir chamadas e aritmetica inteira.
- Escopos lexicos, sombreamento e slots estaveis seguem as regras ja
  implementadas no PR de escopos.
- O analisador rejeita tipos ainda nao suportados nesse backend, como
  `real`, `texto`, `bytes` e `lista[inteiro]`, com **erro 2**.
- Anotacoes incompletas, ausencia de `=` e anotacao em atribuicao
  (em vez de declaracao) sao recusadas com **erro 3**.
- Uma inicializacao sem expressao permanece invalida.

O analisador e compartilhado pelos emissores
`emissao_corpos_funcoes_elf.rts` e `emissao_integrada_elf.rts`, sem
necessidade de inserir logica de tipos duplicada nesses backends.

## Validacao

```sh
python -m unittest testes.test_emissao_corpos_funcoes_elf_rs -v
python -m unittest testes.test_emissao_integrada_elf_rs -v
python -m unittest discover -s testes -v
```

A matriz CI testa ambos os emissores em Windows e Linux, com Python
3.10, 3.11 e 3.14. Os novos testes incluem O0 e O8, ramos alternativos,
laços, sombreamento, chamadas de funcao e erros de tipo/sintaxe. A
execucao dos ELF64 gerados e verificada em Linux x86-64.

## Por que essa etapa importa

O compilador RS que queremos autocompilar usa anotacoes explicitas de
tipos em larga escala. Reconhecer a sintaxe de `inteiro` e um avanco
incremental, mas **nao** significa suporte aos outros tipos usados no
compilador, nem elimina o bootstrap Python. Autocompilacao completa
depende de tipos proprietarios, bytes, listas, registros, imports e
runtime apropriados, alem de um build autorreferente demonstravel.
