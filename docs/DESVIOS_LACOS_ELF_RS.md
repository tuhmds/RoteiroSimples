# Desvios de laço (`pare` e `continue`) no emissor ELF da RS

O subconjunto experimental ELF64 Linux escrito em RoteiroSimples agora
aceita comandos `pare` e `continue` dentro de `enquanto`, tanto
no bloco `inicio` como nos corpos de funções inteiras.

```rs
funcao soma_impares(limite: inteiro) -> inteiro {
    seja i = 0
    seja total = 0
    enquanto i < limite {
        i = i + 1
        se i % 2 == 0 {
            continue
        }
        total = total + i
    }
    retorne total
}
inicio {
    seja resultado = soma_impares(6)
}
```

O resultado do exemplo é **9** (1 + 3 + 5).

## Funcionamento

A representação intermediária usa as novas categorias:
- **9 — `pare`**: sair do `enquanto` mais interno.
- **10 — `continue`**: saltar para a nova avaliação do predicado do
  `enquanto` mais interno.
- **16 — erro de desvio**: `pare`/`continue` fora de laço ou com
  argumento inválido.

O parser conta os laços atualmente abertos e valida cada comando, sem
confundir condicionais aninhadas com laços. Comandos imediatamente após
`pare` ou `continue` no mesmo bloco são rejeitados como código
inalcançável (erro **10**), conservando a análise de retornos existente.

A emissão nativa cria um `jmp rel32` reservado para cada desvio.
O salto é corrigido ao fechar o `enquanto` de destino, com identidade
única por instrução na representação intermediária, de modo que laços
aninhados não confundem os destinos. O salto de `continue` volta ao
predicado; `pare` vai à instrução depois do laço.

## Verificação

```sh
python -m unittest testes.test_emissao_corpos_funcoes_elf_rs -v
python -m unittest discover -s testes -v
```

Há testes O0/O8 com execução ELF64 em Linux x86-64, além de verificações
estruturais no Windows: ramos condicionais, laços aninhados, laço interno
versus externo, código inalcançável e erros de uso fora de laços.

## Limites

Esse recurso pertence ao subconjunto `emissao_corpos_funcoes_elf.rts`
escrito em RS e não altera automaticamente os outros emissores. Ainda
não há compilação integral do compilador pela própria RS: a ferramenta
emissora é compilada inicialmente pelo backend Python. A semântica de
`continue` e `pare` trata apenas `enquanto`; não inclui `para`.
