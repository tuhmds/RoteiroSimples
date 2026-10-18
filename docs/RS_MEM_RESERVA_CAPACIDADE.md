# RS-MEM — Reserva explícita de capacidade dinâmica

Operação pública em português brasileiro:

```text
inicio {
    seja numeros: lista[]
    reserve_capacidade(numeros, 1000)
    para i de 0 ate 999 {
        adicione(numeros, i)
    }
}
```

`reserve_capacidade(dono, minimo)` aceita apenas `lista[T]`,
`texto` e `bytes` dinâmicos com propriedade. O segundo argumento
é uma expressão inteira avaliada uma vez. Para listas, a unidade é
elemento; para texto e bytes, é **byte**, não caractere Unicode.

A reserva aumenta a capacidade se necessário, sem alterar o comprimento.
A política interna pode escolher capacidade maior que o mínimo pedido
(crescimento geométrico). Chamadas menores que a capacidade atual não
encolhem o armazenamento. Negativos, excesso de endereçamento, falhas
de alocação e valores inativos são erros nativos controlados.

Não habilitamos a operação em empréstimos nem buffers fixos. Ela não
transfere propriedade, não cria referências, não permite sobrescrever
índices fora de tamanho e não introduz coleta de lixo ou overcommit
próprio. O armazenamento segue o alocador nativo existente; em Linux,
se a PR RS-MEM anterior estiver integrada, poderá aproveitar `mremap`.

A implementação liga o parser diretamente ao emissor conservador,
que chama a rotina comum `rs_valor_reservar`. Programas com esta
instrução ainda não utilizam automaticamente otimizações SSA completas;
a cobertura intermediária marca o nó como não representado.

Testes: `python -m unittest testes.test_rs_mem_reserva_capacidade -v`.
Toda a suíte em Windows/Linux e níveis O0–O8 permanece obrigatória.
