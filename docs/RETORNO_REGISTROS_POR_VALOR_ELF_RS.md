# Retorno por valor de registros no emissor ELF64 escrito em RS

Este incremento conecta o transporte binario de retorno de registros
introduzido na ABI experimental ao compilador de corpos escrito em RS.
Os campos devem ser inteiros de 64 bits, admitindo registros aninhados
de layout estatico.

## Exemplo

```rs
tipo Ponto {
    x: inteiro
    y: inteiro
}

funcao criar(n: inteiro) -> Ponto {
    seja p: Ponto
    p.x = n
    p.y = 2
    retorne p
}

inicio {
    seja resultado: Ponto
    resultado = criar(40)
    seja soma = resultado.x + resultado.y
}
```

A execucao ELF64 termina com resultado 42.

## ABI experimental

- Uma funcao `-> Registro` retorna os slots do registro por copia.
- O chamador reserva o registro antes da chamada e passa o endereco
  do seu primeiro slot como argumento oculto, empilhado apos os
  argumentos explicitos.
- O argumento oculto fica em `[rbp + 16]` na funcao chamada.
  Os parametros explicitos ficam em `[rbp + 24 + 8*i]`.
- `retorne variavel` copia os slots inteiros da variavel local,
  de um parametro por valor ou de um emprestimo de mesmo tipo
  para o buffer do chamador. A copia ocorre antes do descarte de
  recursos do escopo de retorno.
- O chamador limpa os argumentos, incluindo o ponteiro oculto.
  O retorno nao deixa um valor escalar empilhado.
- A compatibilidade do esquema de registro e verificada
  estaticamente; `Ponto` e `Outro` nao sao intercambiaveis
  ainda que tenham o mesmo numero de slots.

## Limitacoes atuais

- A recepcao do retorno requer uma variavel local ja declarada:
  `seja p: Ponto` seguido de `p = criar(...)`.
- Ainda nao aceita `seja p: Ponto = criar(...)`, `retorne criar(...)`
  nem chamadas que retornam registros dentro de uma expressao inteira.
- Nao ha retorno de campos proprietarios dinamicos, registros com
  textos/listas ou transferencia de ownership.
- O backend continua experimental, apenas Linux ELF64. O emissor
  escrito em RS ainda e construido via bootstrap Python.
- Tipos diferentes, origem nao estruturada, valores escalares usados
  como registros e retorno de registro usado como inteiro sao
  rejeitados na compilacao (erro 18).

## Validacao

```sh
python -m unittest testes.test_retorno_registros_por_valor_elf_rs -v
python -m unittest discover -s testes -v
```

A suite abrange O0/O8, retornos com zero, um e dois argumentos,
registros aninhados, reatribuicoes, caminhos condicionais, copia
de emprestimos, isolamento de parametros por valor e diagnosticos
de incompatibilidade. Windows recompila o emissor escrito em RS;
Linux tambem executa a imagem ELF64 produzida.

## Proximo passo

Apoiar inicializacao tipada por chamada e `retorne outra_funcao()`
com buffers temporarios definidos na IR. A autocompilacao exige
ainda a capacidade de compilar as fontes reais do proprio emissor.
