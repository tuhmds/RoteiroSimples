# Parametros de registros por valor no emissor ELF64 (experimental)

O emissor ELF64 escrito em RS aceita parametros de tipos de registro
declarados, alem de `emprestimo[NomeRegistro]`. A funcao recebe uma **copia
independente** dos campos inteiros do registro, inclusive subregistros
achatados. A assinatura de retorno ainda exige `inteiro`.

## Exemplo

```rs
tipo Ponto {
    x: inteiro
    y: inteiro
}

funcao deslocar(p: Ponto) -> inteiro {
    p.x = p.x + 10
    retorne p.x + p.y
}

inicio {
    seja ponto: Ponto
    ponto.x = 5
    ponto.y = 2
    seja resultado = deslocar(ponto) + ponto.x
}
```

O resultado e 22: `deslocar` produz 17, e `ponto.x` ainda vale 5
no chamador.

## Representacao e propriedade

- Na chamada, um argumento por valor precisa ser um identificador de registro
  do mesmo tipo. O chamador passa o endereco temporariamente.
- O prologo do callee reserva **slots privados** para todos os campos
  (ate 32 por registro), copia as palavras de 64 bits e armazena o endereco
  da copia na posicao do parametro.
- O parametro por valor recebe identificador interno `50 + indice_tipo`.
  O parametro emprestado continua com `40 + indice_tipo`, somente leitura.
- Leituras e escritas do parametro por valor acessam somente a copia local.
  E possivel passar a copia a outra funcao por valor ou emprestimo readonly.
- Um emprestimo readonly do mesmo tipo tambem pode servir de origem de uma
  chamada por valor; a copia e materializada no quadro do destino.
- Misturas com `inteiro` e multiplos registros seguem a ABI de argumentos
  em ordem inversa. A area dos novos registros nao colide com os slots locais.
- Registro com tipo diferente, argumento temporario, retorno do registro
  como inteiro e mutacao de `emprestimo[Registro]` sao rejeitados.

## Limites conhecidos

Somente registros de campos `inteiro` ou subregistros ja declarados.
Nao ha retorno de registro por valor, campos proprietarios dinamicos,
transferencia de propriedade ou recursao. O limite se mantem em oito
parametros, 32 funcoes, ate oito tipos e ate 32 slots por tipo.
O compilador RS do emissor ainda usa bootstrap Python.

## Validacao

```sh
python -m unittest testes.test_parametros_registros_valor_elf_rs -v
python -m unittest testes.test_emprestimo_registros_elf_rs -v
python -m unittest discover -s testes -v
```

Verificar o caminho O0 e O8 em Ubuntu e Windows e executar os testes
nativos ELF64 quando o ambiente suportar. A CI verde nao substitui
auditoria de memoria e ABI para uso em producao.
