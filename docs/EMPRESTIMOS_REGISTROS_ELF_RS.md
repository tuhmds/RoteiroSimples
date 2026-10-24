# Passagem de registros por emprestimo no emissor ELF64 escrito em RS

Uma funcao pode receber `emprestimo[NomeRegistro]` e consultar
os campos do registro original, inclusive caminhos aninhados,
sem fazer copia e sem assumir a propriedade. O registro
deve permanecer vivo durante a chamada; reemprestimos
para outras funcoes com o mesmo tipo sao permitidos.

## Exemplo

```rs
tipo Endereco {
    rua: inteiro
    numero: inteiro
}
tipo Pessoa {
    id: inteiro
    endereco: Endereco
}

funcao consultar(p: emprestimo[Pessoa]) -> inteiro {
    retorne p.id + p.endereco.numero
}

inicio {
    seja pessoa: Pessoa
    pessoa.id = 10
    pessoa.endereco.numero = 7
    seja resultado = consultar(pessoa)
}
```

O resultado e 17.

## ABI e regras

- O proprietario ocupa slots contiguos de 64 bits na pilha.
- O parametro recebe um ponteiro para o primeiro slot do
  registro do chamador, sem fazer copia.
- O acesso `p.endereco.numero` soma os deslocamentos de
  campo resolvidos pela definicao achatada do registro.
- Os tipos de parametro emprestado usam IDs internos
  `40 + indice_tipo`. Um argumento so e aceito se for o
  registro proprietario `7 + indice_tipo` ou outro
  emprestimo de mesmo tipo.
- `p.campo = ...`, `retorne p` como inteiro e argumentos
  de tipos diferentes sao rejeitados na compilacao.
- As referencias nao entram na limpeza automatica de
  propriedade, pois o dono segue no escopo chamador.
- O limite do backend continua sendo de ate oito parametros
  por funcao e ate 32 funcoes. Nao inclui ainda retorno
  de registros por valor nem transferencia de propriedade.

## Validacao

```sh
python -m unittest testes.test_emprestimo_registros_elf_rs -v
python -m unittest discover -s testes -v
```

Os testes O0/O8 exercitam leitura de campos, sub-registros,
reemprestimo, parametros inteiros intercalados, mudanca do
proprietario apos a consulta e rejeicoes de tipo e mutacao.

O emissor ainda depende de bootstrap Python e somente produz
o executavel nativo ELF64 experimental no Linux x86-64.
