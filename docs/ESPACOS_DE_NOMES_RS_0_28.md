# RS 0.28 — Espaços de nomes e visibilidade

Os módulos podem ser importados com apelidos para evitar conflitos entre bibliotecas que utilizem os mesmos nomes.

## Sintaxe

No arquivo principal:

```text
importe "financeiro.rts" como financeiro
importe "estoque.rts" como estoque

inicio {
    seja pedido: financeiro.Pedido
    pedido.valor = 25
    escreva(financeiro.calcular(pedido))
}
```

No arquivo importado:

```text
publico tipo Pedido {
    valor: inteiro
}
privado funcao taxa(x: inteiro) -> inteiro {
    retorne x + 5
}
publico funcao calcular(p: Pedido) -> inteiro {
    retorne taxa(p.valor)
}
```

**publico** expõe funções ou tipos aos importadores. **privado** limita o acesso ao próprio módulo. Para preservar a compatibilidade, definições sem modificador são públicas. A importação com apelido exige qualificação, como `financeiro.calcular` e `financeiro.Pedido`. O comando histórico `importe "arquivo.rts"` continua expondo símbolos públicos diretamente, inclusive os provenientes de importações sem apelido.

As definições são reunidas na compilação e produzem um único executável nativo. O mesmo arquivo é incluído uma única vez, mesmo importado sob dois apelidos. Os caminhos são relativos, devem permanecer dentro do projeto e usar extensão `.rts`. Importações circulares são rejeitadas.

O compilador distingue tipos nominais e funções de módulos diferentes, verifica conflitos de apelidos, impede acesso a símbolos privados e preserva as localizações originais para diagnósticos. Literais UTF-8 permanecem intactos.

Ainda não há memória dinâmica, distribuição de pacotes, interfaces genéricas nem análise avançada entre funções. O compilador é experimental e não é recomendado para produção.

Comandos e nomes técnicos novos usam português brasileiro sem acentos; mensagens e documentação podem usar acentuação normal.
