# Registros aninhados no emissor ELF64 escrito em RS

O emissor experimental aceita registros compostos de campos `inteiro`
e de outros registros ja declarados. O layout de cada registro e
achatado em inteiros signed64 contiguos na pilha ou em uma lista
dinamica. Isso nao representa ainda o compilador autocompilado.

## Exemplo

```rs
tipo Coordenada {
    x: inteiro
    y: inteiro
}
tipo Local {
    id: inteiro
    posicao: Coordenada
    codigo: inteiro
}
funcao executar() -> inteiro {
    seja lugar: Local
    lugar.posicao.x = 10
    lugar.posicao.y = 8
    retorne lugar.posicao.x + lugar.posicao.y
}
inicio { seja resultado = executar() }
```

O registro Local usa quatro slots de 8 bytes: id, posicao.x,
posicao.y e codigo. Um caminho completo, como `lugar.posicao.y`,
e resolvido em tempo de compilacao. Somente campos inteiros finais
podem ser lidos ou alterados como escalares; `lugar.posicao`
sozinho nao pode ser convertido para inteiro.

## Limites e seguranca

- Ate 8 tipos por unidade, ate 8 campos nomeados por tipo e ate
  32 slots de 64 bits por registro achatado.
- Tipos usados como campos devem ter sido declarados anteriormente.
  Isso permite aninhamento em varias camadas sem tipos ciclicos.
  Tipos desconhecidos ou declarados depois do uso recebem erro 2.
- Atribuicoes sao por campo, sem inicializadores de registro,
  copias integrais ou retornos estruturados.
- Listas `lista[Local]` continuam dinamicas, com `mmap` e
  `mremap`, usando o tamanho total achatado como passo de acesso.
- `adicione(lista, registro)` copia todos os slots, inclusive os
  campos internos, mantendo a memoria sob responsabilidade da lista.
- `emprestimo[lista[Local]]` continua read-only e nao pode alterar
  campos aninhados; indice invalido termina com `exit(23)`.
- O limite de 128 slots no quadro de cada funcao e mantido.
- Os erros de campo inexistente, tipo incompatível e registro
  inteiro usado como escalar sao preservados.

## Testes

```sh
python -m unittest testes.test_registros_aninhados_elf_rs -v
python -m unittest discover -s testes -v
```

A suite cobre O0/O8, registros com 2 e 3 camadas, campos zerados,
atribuicoes e expressoes, escopos, listas com crescimento,
emprestimos de listas e erros de tipo/caminho.

## Proximo passo

Passar **registros inteiros entre funcoes** com semantica de copia
ou emprestimo de leitura, mantendo ownership e ABI explicitos.
O emissor escrito em RS ainda depende do bootstrap Python.
