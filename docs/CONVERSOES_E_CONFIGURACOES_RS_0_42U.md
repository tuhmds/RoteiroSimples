# RS 0.42U — conversões e configurações escritas em RS

## Contrato das conversões

O módulo `padrao/conversoes.rts` acrescenta duas operações explícitas, sem
alterar os tipos, a sintaxe ou as funções numéricas existentes. Separar o
módulo evita carregar conversões de textos em programas que importam apenas
`padrao/numeros.rts`. O compilador continua em Python e gera PE/ELF diretamente.

| Operação | Retorno | Contrato |
| --- | --- | --- |
| `inteiro_de_texto(origem: emprestimo[texto])` | `resultado[inteiro]` | Decimal ASCII `[+-]?[0-9]+`, dentro de -9223372036854775808 a 9223372036854775807 |
| `texto_de_inteiro(valor: inteiro)` | `resultado[texto]` | Decimal canônico, sem `+` ou zeros adicionais; zero é `0` |

`inteiro_de_texto` não apara espaços implicitamente. Aceita zeros iniciais,
inclusive em textos longos; `-0` vale zero. Recusa dígitos Unicode, separadores,
sufixos, NUL, expoentes, prefixos hexadecimais e sinais sem dígitos.

| Código de `inteiro_de_texto` | Significado |
| --- | --- |
| 1 | Texto vazio |
| 2 | Formato inválido |
| 3 | Fora do intervalo de inteiro |

Um caractere inválido prevalece sobre um excesso anterior de dígitos. A
operação percorre toda a entrada quando detecta excesso, sem continuar os
cálculos que poderiam transbordar. A acumulação permanece negativa, com
limites conferidos antes de multiplicar/subtrair; o mínimo de 64 bits não
precisa de valor absoluto nem de um inteiro positivo intermediário impossível.
A consulta usa espaço auxiliar constante e não aloca conteúdo próprio.

`texto_de_inteiro` também trabalha com valores negativos para formatar o
mínimo. O resto da divisão segue o sinal do dividendo, com quociente truncado
em direção a zero. Dois buffers locais de 20 bytes bastam para os 19 dígitos
e o sinal permitidos pelo tipo; o texto devolvido é um dono novo. A conversão
reutiliza `decodifique_utf8` e propaga seu resultado (código 1 se recusado).
Os bytes gerados são ASCII; não existe erro de domínio numérico para um
`inteiro`. Falta de memória conserva o encerramento nativo, sem se tornar
um erro recuperável destas funções.

```text
importe "padrao/conversoes.rts" como conversoes
inicio {
    seja origem: texto = "+00042"
    seja numero = conversoes.inteiro_de_texto(empreste(origem))
    se numero.valido {
        seja escrito = conversoes.texto_de_inteiro(numero.valor)
        se escrito.valido {
            escreva(escrito.valor)
        }
    }
}
```

## Aparar espaços explicitamente

`textos.aparar(origem: emprestimo[texto]) -> resultado[texto]` cria uma cópia
sem os bytes ASCII 9..13 e 32 nas extremidades: tabulação, LF, VT, FF, CR e
espaço. Espaços internos são preservados. NUL, espaço inseparável e demais
caracteres Unicode não são removidos. A operação mantém o contrato de UTF-8
e de valores escalares das demais funções do módulo.

Para aceitar espaços em uma entrada numérica, chame `textos.aparar` antes de
`conversoes.inteiro_de_texto`. Não há conversão implícita de texto para número.

## Biblioteca de linhas de configuração

`padrao/configuracoes.rts` fornece:

```text
publico tipo EntradaNumerica {
    ignorada: logico
    chave: texto
    valor: inteiro
}
```

`linha_numerica(origem: emprestimo[texto]) -> resultado[EntradaNumerica]`
interpreta uma linha `chave=inteiro`, aparando espaços ASCII nas extremidades
da linha, da chave e do valor. A chave tem dono próprio; a origem permanece
disponível. Linhas vazias ou cujo primeiro caractere após aparar seja `#`
devolvem sucesso com `ignorada=verdadeiro`. A chave não pode ser vazia.

Os códigos 1..3 vêm da conversão numérica; 4 significa ausência de `=` e 5,
chave vazia. A verificação da estrutura/chave antecede a conversão do valor.
O primeiro `=` separa os campos; outro `=` no valor causa formato numérico
inválido. Não há comentários ao final do valor, aspas, escapes do formato,
seções, esquema de chaves ou política automática para chaves repetidas.
O chamador decide como guardar entradas e resolver repetições.

O [exemplo nativo](../exemplos/ferramentas/configuracao_numerica_rs042u.rts)
lê `configuracao_numerica.txt` como bytes e decodifica UTF-8 com resultado
explícito. Imprime chave e inteiro normalizado em linhas separadas. Indica
a linha e o código de erro; encerra com status 2. Entradas anteriores podem
ter sido impressas. A consulta inicial não elimina a corrida até a leitura:
falhas posteriores conservam o contrato nativo de E/S. Não é um leitor INI
completo, um banco de dados ou uma operação atômica sobre o arquivo.

## Verificação

São 14 testes portáveis, com execução nativa em O0–O8 e compilação PE/ELF:
limites de 64 bits, sinais, zeros iniciais, entradas longas, potências de dez
e vizinhos, 64 valores gerados com semente fixa, caracteres recusados,
prioridade dos erros, cópias, empréstimos de campos/listas, propagação,
coleções proprietárias e dez casos de arquivo. Os oráculos usam `int`, `str`,
expressão regular ASCII, `strip` com conjunto explícito e soma Python.

O teste de aparar compara o conteúdo dentro do executável RS e confere
bytes/caracteres, preservando CR internos sem depender da normalização de
quebras de linha realizada pela captura de saída do processo.

Um ensaio Windows isolado intercepta alocação/liberação e chama o código
com sentinelas: uma origem reutilizada, três formatações, leituras válidas
e inválidas, quatro alocações/quatro liberações, oito registradores inteiros,
dez vetoriais e RSP preservados. Essa contagem pertence ao caso ensaiado,
sem ser uma prova geral de segurança de memória.

```text
python -m unittest testes.test_conversoes_rs042u testes.test_abi_conversoes_rs042u -v
python compilar.py exemplos/ferramentas/configuracao_numerica_rs042u.rts -O 8 -o configuracao.exe
python -m benchmarks.medir --fonte benchmarks/conversoes_rs042u.rts --repeticoes 17 --json conversoes.json
```

O benchmark faz duas mil idas e voltas, de -1000 a 999, e deve imprimir
`-1000`. A CI mede os nove níveis com 17 amostras intercaladas, além dos sete
benchmarks anteriores. Tempos incluem a inicialização do processo. Os corpos
com donos/buffers continuam conservadores; O8 não garante aceleração.

Esta etapa não altera o contrato público mutável de `resultado[T]`, não
introduz reais/decimais e não substitui a avaliação independente do front-end.
