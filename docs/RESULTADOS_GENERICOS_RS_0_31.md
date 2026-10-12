# Resultados genéricos e propagação explícita — RS 0.31

## O que realmente foi implementado

A sintaxe de resultados genéricos é reconhecida na etapa de compilação e especializada
para tipos concretos. O programador escreve resultado[T]; o compilador cria um
registro concreto e dois construtores próprios para cada T utilizado no projeto.

Os três componentes são:
- resultado[T]: registro com valido: logico, valor: T, codigo_erro: inteiro;
- sucesso[T](valor): construtor que devolve um resultado válido com código zero;
- falha[T](codigo): construtor que devolve um resultado inválido e valor inicializado com zero.
  Se codigo for zero, converte-o para 2 (fora do domínio), evitando marcar falha sem código.

A especialização acontece antes da análise estática existente, portanto os parâmetros,
os retornos, as cópias de registros e as chamadas permanecem verificados pelo sistema
de tipos do compilador. Não há objeto genérico alocado em tempo de execução, reflexão,
instruções Python embutidas no executável nem dependência de bibliotecas dinâmicas da RS.

## Exemplo

```text
funcao dividir(a: inteiro, b: inteiro) -> resultado[inteiro] {
    se b == 0 {
        retorne falha[inteiro](1)
    }
    retorne sucesso[inteiro](a / b)
}

funcao calcular(n: inteiro, divisor: inteiro) -> resultado[inteiro] {
    seja parte = dividir(n, divisor)
    propague parte
    retorne sucesso[inteiro](parte.valor + 5)
}

inicio {
    seja a = calcular(20, 2)
    escreva(a.valor)

    seja b = calcular(20, 0)
    escreva(b.valido)
    escreva(b.codigo_erro)
}
```

O programa imprime 15, 0 e 1 em linhas separadas.

O comando `propague nome` é **explícito**: se nome.valido for falso, a função atual
retorna falha[T](nome.codigo_erro), sendo T o tipo de retorno da função atual.
Caso o resultado seja válido, a execução continua. Para acessar o valor,
utilize nome.valor. O comando só é permitido dentro de uma função que
retorne resultado[T]; fora desse contexto, é erro de compilação.

O tipo do resultado que será propagado pode diferir do tipo de retorno da função
atual. Por exemplo, uma função que retorna resultado[logico] pode propagar uma falha
de resultado[inteiro], preservando o código de erro.

## Tipos compatíveis

- resultado[inteiro] e resultado[logico].
- resultado[MeuRegistro], inclusive quando o registro veio de um módulo importado.
- resultado[texto[32]] e resultado[lista[5]] com capacidade/tamanho explícitos.

Cada especialização é distinta. resultado[inteiro] não aceita sucesso[logico](verdadeiro).
O tamanho faz parte do tipo: resultado[texto[32]] é diferente de resultado[texto[64]].

O registro de resultado contém campos públicos, mutáveis e copiados por valor.
A compatibilidade com campos e códigos das funções da Biblioteca Padrão RS 0.30 é
intencional; entretanto, ResultadoInteiro (RS 0.30) e resultado[inteiro] (RS 0.31)
**não são o mesmo tipo nominal**, e não há conversão implícita entre eles.

## Sintaxe, segurança e limitações

- O tipo T deve ser **concreto**: inteiro, logico, registro próprio previamente
  declarado, texto[N] ou lista[N]. Não há declaração genérica de funções
  pelo programador nem resultados aninhados resultado[resultado[T]].
- Não há sintaxe de acesso direto a campos do retorno de uma função.
  Guarde antes numa variável: seja resposta = dividir(10, 2).
- Propagação explícita não captura transbordamentos aritméticos nem falhas nativas
  de índice, capacidade ou sistema operacional. Esses erros continuam usando
  o comportamento seguro de encerramento já implementado.
- Não há exceções, pilha dinâmica de resultados, referências nem alocação no heap.
- As formas históricas ResultadoInteiro e ResultadoLogico da RS 0.30
  continuam funcionando sem modificações.
- As especializações são inseridas antes das funções na unidade de compilação;
  resultados genéricos de tipos declarados em módulos respeitam as regras
  atuais de importação, visibilidade e identidade nominal.
- Identificadores e comandos sob controle da RS estão em português brasileiro
  **sem acentos**; documentação, diagnósticos e literais podem utilizar UTF-8.
- Os níveis de otimização -O 0 a -O 8 permanecem iguais. Sem nível novo.

## Como executar e testar

Windows:

```powershell
py -3 compilar.py exemplos\resultados_genericos.rts --alvo windows -O 8 -o roteiro_windows.exe
.\roteiro_windows.exe
py -3 -m unittest discover -s testes -v
```

Linux:

```bash
python3 compilar.py exemplos/resultados_genericos.rts --alvo linux -O 8 -o roteiro_linux
./roteiro_linux
python3 -m unittest discover -s testes -v
```

A RS permanece experimental e não deve ser usada em produção.
