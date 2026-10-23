# Chamadas futuras acíclicas no emissor ELF escrito em RS

O emissor experimental `biblioteca_padrao/emissao_corpos_funcoes_elf.rts`
aceita agora a chamada de uma função que aparece **mais adiante no arquivo**,
desde que as dependências entre funções não contenham ciclos.

```rs
funcao executar(n: inteiro) -> inteiro {
    retorne aumentar(n) + 1
}
funcao aumentar(n: inteiro) -> inteiro {
    retorne n * 2
}
inicio {
    seja resultado = executar(5)
}
```

O programa é aceito pelo subconjunto ELF64 Linux escrito em RoteiroSimples.
A resolução de `call rel32` é feita **depois** de gerar o código de todas
as funções, usando os endereços reais já existentes no emissor.

## Verificação de dependências sem recursão

Cada ligação de chamada registra a função de origem, o destino e a posição
do token da chamada. A origem **-1** é o bloco `inicio`, que não compõe
ciclos entre funções.

Depois da emissão, uma matriz de até **16 × 16** elementos representa
as chamadas realmente emitidas. O fechamento transitivo detecta ciclos,
inclusive entre três ou mais funções e quando a chamada aparece em um
`se`, `senao` ou `enquanto`.

- Código **12**: função chamada não existe.
- Código **13**: quantidade de argumentos incompatível.
- Código **14**: recursão direta ou indireta, com posição de uma chamada
  participante do ciclo.
- Código **15**: chamada sintaticamente malformada.

A validação de assinaturas continua limitada a parâmetros e resultados
`inteiro`. Recursão não é habilitada, nem mesmo em ramos que pareçam
inacessíveis em tempo de execução: a análise é deliberadamente conservadora.

## Validação

```sh
python -m unittest testes.test_emissao_corpos_funcoes_elf_rs -v
python -m unittest discover -s testes -v
```

O teste usa os níveis O0 e O8 para combinações de chamadas anteriores
e posteriores, chamadas em predicados, laços, argumentos aninhados,
erros de aridade, funções inexistentes e ciclos indiretos. No Linux x86-64
também executa os binários ELF gerados.

## Limites

Este incremento **não é autocompilação concluída**. O emissor é escrito
em RS, mas o executável do emissor ainda é construído com o compilador
de desenvolvimento em Python. Este backend parcial continua produzindo
ELF64 Linux e mantém as restrições do subconjunto descritas nos demais
documentos.
