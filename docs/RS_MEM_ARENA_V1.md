# RS-MEM — arena reutilizável de bytes (fase inicial)

Módulo em código-fonte **RS real**: `importe "padrao/arenas.rts" como arenas`.
Depende da operação `reserve_capacidade` introduzida no PR #31.
Esta é uma etapa de baixo risco da estratégia de alocação por regiões:
não substitui o alocador nativo compartilhado e não altera a ABI.

## Contrato

O tipo `arenas.Arena` possui um buffer `bytes` e um cursor lógico.
A API permite `criar(capacidade)`, `acrescentar(arena, byte)`,
`ler(empreste(arena), indice)`, `marca(empreste(arena))`,
`recuar(arena, marca)`, `reiniciar(arena)`,
`tamanho(empreste(arena))`, `capacidade(empreste(arena))` e
`reservar(arena, minimo)`.

Operações mutáveis **consomem** a arena e devolvem seu dono sem duplicar
a região; a chamada de função e a transferência do registro têm custo.
Marcas são inteiros (offsets em bytes), não ponteiros nem referências.
`recuar` exige um marcador entre 0 e `usados` ou encerra com erro.
`reiniciar` zera o cursor lógico, conservando o armazenamento físico.
Futuras gravações reutilizam as posições existentes. O comprimento físico
de `dados` pode ser maior que a parte logicamente ativa da arena, mas
`ler` recusa acesso fora de `[0, usados)` com `resultado[inteiro]`
e código 1, evitando expor dados obsoletos pela API.

As operações de byte continuam verificadas pelo backend. O módulo
não é seguro para acessos simultâneos e não implementa um heap geral,
blocos de tamanho variável, RAII especial, pointers persistentes,
movimentação arbitrária de objetos ou pools concorrentes. Não substitui
uma auditoria completa de segurança; usar campos internos diretamente
burlaria a validação lógica enquanto o registro público estiver mutável.

## Exemplo e testes

Exemplo: `exemplos/aplicacoes/arena_memoria_rs_mem.rts`.
Testes: `python -m unittest testes.test_rs_mem_arena -v` em Windows e
Linux. Cobrem crescimento, reuso sem perda de capacidade, marcador inválido,
resultado recuperável e compatibilidade em O0/O4/O8.

Esta implementação usa a infraestrutura já existente e pode ser combinada
com o uso de `mremap` do PR #30, mas não depende dela. Em estágios posteriores,
um alocador genérico deve ter metadados privados e sincronização adequada,
mantendo o contrato de propriedade e empréstimos.
