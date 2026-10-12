# Biblioteca Padrão RoteiroSimples — RS 0.29

## Finalidade

A RS 0.29 apresenta a primeira **Biblioteca Padrão executável escrita na própria RS**, sem dependência do Python durante a execução. O compilador lê os módulos distribuídos em `biblioteca_padrao/`, resolve seus tipos e funções na compilação e gera um executável nativo como antes.

Sintaxe oficial:

```text
importe "padrao/numeros.rts" como numeros
importe "padrao/matematica.rts" como matematica
importe "padrao/estatistica.rts" como estatistica
importe "padrao/listas.rts" como listas
```

O caminho `padrao/` é uma localização reservada para módulos fornecidos junto com o compilador. As importações relativas de projetos continuam restritas à pasta do projeto; um módulo da Biblioteca Padrão só pode importar arquivos permitidos dentro da própria biblioteca. Não se utiliza Python para calcular os resultados das funções RS em tempo de execução.

## Catálogo de funções públicas

### `numeros` — 9 funções

| Função | Resultado |
| --- | --- |
| `menor(a, b)` | menor inteiro |
| `maior(a, b)` | maior inteiro |
| `absoluto(valor)` | módulo matemático |
| `sinal(valor)` | -1, 0 ou 1 |
| `limitar(valor, inferior, superior)` | aproxima dos limites |
| `eh_par(valor)` | lógico |
| `eh_impar(valor)` | lógico |
| `quadrado(valor)` | produto pelo próprio valor |
| `multiplo_de(valor, divisor)` | lógico; divisor zero retorna falso |

`limitar` pressupõe `inferior <= superior`. `absoluto` aplicado ao menor inteiro de 64 bits produz erro de transbordamento nativo, nunca um valor incorreto.

### `matematica` — 8 funções

| Função | Regra |
| --- | --- |
| `potencia_natural(base, expoente)` | potência com expoente inteiro não negativo; expoente negativo retorna 0 |
| `fatorial(n)` | 0 a 20; fora desse intervalo retorna -1 |
| `fibonacci(n)` | índices 0 a 92; fora desse intervalo retorna -1 |
| `mdc(a,b)` | máximo divisor comum, entradas não negativas; negativo retorna -1 |
| `mmc(a,b)` | mínimo múltiplo comum, entradas não negativas; negativo retorna -1, e zero retorna 0 |
| `eh_primo(n)` | lógico, rejeita n menor que 2 |
| `soma_digitos(n)` | soma dos algarismos decimais de n não negativo; negativo retorna -1 |
| `quantidade_digitos(n)` | quantidade decimal sem sinal; zero conta como um dígito |

Os cálculos inteiros mantêm o erro nativo por transbordamento. Não há função de potências com resultados reais nesta etapa.

### `estatistica` — 6 funções, listas `lista[5]`

`soma_cinco`, `media_cinco`, `minimo_cinco`, `maximo_cinco`, `amplitude_cinco`, `contar_acima_cinco(valores,limite)`.

A média é **inteira com truncamento para zero**. O somatório pode transbordar mesmo quando a média matemática caberia em 64 bits; isso continua sendo erro nativo. A amplitude também verifica o transbordamento.

### `listas` — 7 funções, listas `lista[5]`

`buscar_cinco(valores,procurado)` (posição inicial, ou -1), `contar_cinco`, `contem_cinco`, `crescente_cinco` (não decrescente), `inverter_cinco`, `ordenar_cinco` (ordem crescente) e `substituir_cinco`.

As três últimas devolvem **uma lista nova**, sem modificar a lista do chamador. Tipos e capacidades são verificados estaticamente. Os índices continuam verificados em execução.

## Exemplo e testes

```powershell
py -3 compilar.py exemplos\biblioteca_padrao.rts --alvo windows -O 8 -o biblioteca_rs.exe
.\biblioteca_rs.exe
py -3 -m unittest discover -s testes -v
```

No Linux, utilize `python3 compilar.py exemplos/biblioteca_padrao.rts --alvo linux -O 8 -o biblioteca_rs` e execute `./biblioteca_rs`.

O projeto principal pode estar em qualquer diretório; os módulos `padrao/` são resolvidos pela instalação do compilador. Não copie a Biblioteca Padrão para cada projeto, e não mova somente `compilar.py` sem os demais arquivos do compilador.

## Limitações e decisões

- A RS ainda tem `inteiro` de 64 bits e `logico`; números reais e decimais são posteriores.
- Não existem parâmetros genéricos `lista[N]`. A primeira biblioteca demonstra o formato `lista[5]` sem fingir que as listas são dinâmicas.
- Erros de domínio com retorno de sentinela (como `fatorial(-1)`) são **convenções temporárias documentadas**, até termos resultados tipados/erros definidos.
- Ainda não há API de arquivos, rede, datas, memória dinâmica ou textos avançados. Serão implementadas com primitivas próprias e testes por sistema operacional, sem criar módulos vazios.
- O código dos módulos está em português brasileiro sem acentos nos identificadores, com comentários e documentação em português brasileiro.
- Os níveis de otimização históricos foram preservados: `-O 0` a `-O 8`; a RS 0.29 não cria outros níveis.
- O RoteiroSimples continua experimental, sem garantias de uso em produção.

## Próximos fundamentos

Para generalizar as bibliotecas de listas e estatística, precisamos de tamanhos dinâmicos, operações de erro explícitas, tipos paramétricos e um modelo de memória com propriedade dos valores. O desenvolvimento dessas capacidades tem precedência sobre mais níveis de otimização.
