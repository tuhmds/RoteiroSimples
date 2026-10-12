# Fluxo de dados e otimização O2 — RS 0.11

> **Versão experimental.** A análise não transforma a IR em SSA e não realiza alocação de registradores.

## Componentes implementados

O módulo `compilador/fluxo_dados.py` lê os **blocos reais do CFG** da RS 0.10 e calcula, por ponto fixo (com ciclos):

- **Definições alcançantes**: quais atribuições a variáveis podem chegar a cada bloco; toda definição recebe identificador de bloco (como `b6:pontos`).
- **Vivacidade (liveness)**: quais variáveis podem ser utilizadas antes de receber novo valor nos caminhos seguintes.
- **Dominadores**: quais blocos aparecem obrigatoriamente em todos os caminhos desde a entrada.
- **Possíveis junções `phi`**: quando múltiplas definições da mesma variável chegam a um bloco por caminhos diferentes (inclusive retorno de laços). **Não geramos nós SSA nem substituímos o backend**; isso é diagnóstico e preparação para uma transformação posterior.
- **Possíveis usos sem definição**: aviso conservador caso não haja definição alcançante para uma variável usada. Ainda não é análise completa de inicialização definida em *todos* os caminhos, e não é erro de compilação.
- Blocos inatingíveis são preservados para inspeção, mas excluídos do ponto fixo dos blocos alcançáveis.

`para` exige atenção: o CFG contém três blocos diferentes para o início (`def` do contador), a condição (`uso` do contador e do limite) e o incremento (`uso` e `def` do contador). `continue` aponta para o incremento, não para o começo do corpo.

### Como inspecionar o fluxo

```powershell
py -3 compilar.py exemplos\fluxo_dados.rts --alvo windows --mostrar-fluxo --salvar-fluxo analise.json -O 2 -o roteiro_windows.exe
.\roteiro_windows.exe
```

`--mostrar-fluxo` lista blocos, variáveis usadas/definidas, entrada e saída vivas, e junções candidatas a `phi`. `--salvar-fluxo` exporta JSON UTF-8 para outras ferramentas. `--mostrar-cfg` e `--salvar-cfg fluxo.dot` continuam disponíveis.

## Níveis de otimização

| Nível | Regras |
|---|---|
| `-O 0` | Sem dobramento de constantes, saída idêntica à RS 0.10. |
| `-O 1` (padrão) | Dobramento de constantes sem suprimir operações que poderiam falhar, compatível com RS 0.10. |
| `-O 2` (experimental) | O1 + substituição de variáveis com valores constantes conhecidos **somente em sequências retas**, dentro do mesmo bloco de instruções. |

Por exemplo, no mesmo trecho sequencial `seja a = 2; seja b = a * 3 + 4; escreva(b)`, O2 substitui `b` por `10` **na expressão compilada**. Atribuições continuam presentes. Não elimina leituras, impressões, acessos ou operações que poderiam falhar.

**Regra conservadora:** valores constantes não atravessam decisões ou laços, e `leia(variavel)` invalida a constante associada à variável lida. Por isso o otimizador não afirma conhecer o resultado de `se`, `enquanto` ou `para` quando existem caminhos diferentes. Não executa análise global de propagação de constantes.

### Segurança aritmética

Não são feitas simplificações que mascarariam estouro de inteiro, divisão por zero ou `-9223372036854775808 / -1`. Operações que poderiam falhar continuam no executável, com os mesmos códigos de saída e mensagens. Os testes comparam O0/O1/O2 em execução nativa, com entradas, laços e erros.

## Limites conhecidos

- `phi?` indica **candidato a junção**, não uma operação SSA real; precisamos de SSA com renomeação de variáveis e integração ao backend para desenvolver CSE/DCE e alocação de registradores baseada na vivacidade.
- Ainda não há segurança geral de memória, ponteiros ou heap.
- A atual IR não possui representação de chamada de funções criada pelo usuário.
- O0 e O1 preservam a geração de binários existentes. O2 **pode mudar o tamanho e os bytes**, e por isso é explicitamente opcional.
- Nenhuma alegação de velocidade deve ser feita sem benchmarks medidos.

## Próximos trabalhos

1. Construir SSA verdadeira sobre CFG, com nós `phi`, verificação de dominância e regras de renomeação.
2. Registrar usos e definições em instruções explícitas para o futuro alocador de registradores.
3. Introduzir eliminação de código morto somente após analisar os efeitos e possíveis exceções.
4. Medir tempo e tamanho em Linux e Windows e comparar O0, O1 e O2 sob condições reproduzíveis.
