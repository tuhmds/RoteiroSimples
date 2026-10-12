# Resultados tipados e tratamento explícito de erros — RS 0.30

## Objetivo

Permitir que funções comuniquem **sucesso ou falha como valores tipados**, sem esconder os erros em números especiais como `-1`. A primeira implementação é feita **na Biblioteca Padrão, em RoteiroSimples**, reutilizando registros, retorno por valor e módulos. Não é um novo tipo genérico da gramática e não há exceções ou captura automática de falhas nesta versão.

As interfaces legadas permanecem para compatibilidade. Prefira as versões do módulo `matematica_segura` quando for necessário distinguir valores válidos de erros de domínio.

## Exemplo prático

```text
importe "padrao/matematica_segura.rts" como segura
importe "padrao/resultados.rts" como resultados

inicio {
    seja resposta: resultados.ResultadoInteiro = segura.dividir(10, 0)

    se resposta.valido {
        escreva(resposta.valor)
    } senao {
        escreva("A operacao falhou")
        escreva(resposta.codigo_erro)
    }
}
```

O exemplo imprime uma mensagem de erro e o código `1`. O retorno é uma cópia do registro: alterar uma cópia não modifica o original.

## Tipos definidos em padrao/resultados.rts

- `ResultadoInteiro`: campos `valido: logico`, `valor: inteiro`, `codigo_erro: inteiro`.
- `ResultadoLogico`: mesmos campos, mas `valor: logico`.

Tipos diferentes **não são intercambiáveis**; uma função que retorna `ResultadoLogico` não pode inicializar uma variável `ResultadoInteiro`.

Construtores e auxiliares públicos:

- `sucesso_inteiro(valor)`, `falha_inteiro(codigo)`.
- `sucesso_logico(valor)`, `falha_logica(codigo)`.
- `inteiro_ou(resultado, padrao)`, `logico_ou(resultado, padrao)`, para fornecer valor alternativo explicitamente.
- `erro_nenhum()`, `erro_divisao_zero()`, `erro_fora_dominio()`, `erro_transbordamento()`, `erro_intervalo_invalido()`.

Convenção da Biblioteca Padrão: sucesso tem `valido=verdadeiro` e `codigo_erro=0`; falha tem `valido=falso`, `valor` zerado e `codigo_erro` não nulo. Os campos são públicos e mutáveis, portanto essa convenção **não é imposta pelo sistema de tipos**; use os construtores em vez de preencher campos manualmente.

| Código | Significado |
|---:|---|
| 0 | Nenhum erro |
| 1 | Divisão ou resto por zero |
| 2 | Argumento fora do domínio permitido |
| 3 | Transbordamento antecipadamente identificado |
| 4 | Intervalo inválido |

## Operações em padrao/matematica_segura.rts

| Operação | Resultado | Falhas representadas |
|---|---|---|
| `dividir(a,b)` | Inteiro | divisor 0; inteiro mínimo dividido por -1 |
| `resto(a,b)` | Inteiro | divisor 0; inteiro mínimo com divisor -1 |
| `fatorial(n)` | Inteiro | fora de 0..20 |
| `fibonacci(n)` | Inteiro | fora de 0..92 |
| `mdc(a,b)` | Inteiro | argumentos negativos |
| `mmc(a,b)` | Inteiro | argumentos negativos |
| `potencia_natural(base,expoente)` | Inteiro | expoente negativo |
| `raiz_quadrada_inteira(n)` | Inteiro | argumento negativo |
| `eh_primo(n)` | Lógico | argumento negativo |
| `limitar(valor,inferior,superior)` | Inteiro | inferior maior que superior |

A raiz quadrada inteira devolve **a parte inteira da raiz**, usando busca binária e comparação por divisão para evitar transbordamento de quadrados. `raiz_quadrada_inteira(15)` devolve 3. `fatorial(0)` devolve 1 e `fibonacci(0)` devolve 0.

## Limitações importantes

- As verificações tipadas de domínio são explícitas, mas **nem todos os transbordamentos aritméticos são convertidos em resultados**. Por exemplo, multiplicações muito grandes em `potencia_natural` e `mmc` ainda encerram a execução pela proteção nativa. O registro de erro não pode recuperar esse encerramento.
- O código 3 é identificado previamente apenas nas operações de divisão/resto para o caso extremo do inteiro mínimo com divisor -1.
- Não há operadores automáticos de propagação de erro, variantes algébricas genéricas, imutabilidade dos resultados, tratamento global de erros ou `resultado[T]` nativo.
- Os resultados `ResultadoInteiro` e `ResultadoLogico` são **nominalmente distintos**. Textos e listas como valores de resultados ficam para o sistema genérico futuro.
- Não houve criação de novo nível de otimização. O código é escrito em PT-BR, com identificadores sem acentos; textos e comentários aceitam UTF-8.
- O compilador RS permanece experimental e não deve ser usado em produção.

## Execução e testes

No Windows:

```powershell
py -3 compilar.py exemplos\resultados_tipados.rts --alvo windows -O 8 -o roteiro_windows.exe
.\roteiro_windows.exe
py -3 -m unittest discover -s testes -v
```

No Linux:

```bash
python3 compilar.py exemplos/resultados_tipados.rts --alvo linux -O 8 -o roteiro_linux
./roteiro_linux
python3 -m unittest discover -s testes -v
```

O teste automatizado `testes/test_resultados_tipados.py` exercita os caminhos de sucesso e falha e a tipagem em executáveis nativos. As funções e resultados se incorporam ao binário final: não exigem Python em tempo de execução.
