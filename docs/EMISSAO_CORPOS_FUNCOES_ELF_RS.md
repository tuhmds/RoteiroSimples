# IR e emissao ELF de corpos de funcao na propria RS

Esta etapa expande a IR da PR #46 para o interior das funcoes. A
ferramenta `exemplos/ferramentas/compilador_corpos_funcoes_elf_rs.rts`,
escrita em RoteiroSimples, consome `codigo_fonte.rts` e grava
`resultado_corpos_elf` (ELF64 x86-64 Linux). O Python atual e usado
**somente** para construir essa ferramenta, ainda nao autocompilada.

## Exemplo admitido

```text
funcao anterior(x: inteiro) -> inteiro {
    retorne x - 1
}

funcao contar(n: inteiro) -> inteiro {
    seja valor = anterior(n)
    enquanto valor < n + 4 {
        se valor == 10 {
            retorne 99
        }
        valor = valor + 1
    }
    retorne valor
}

inicio {
    seja resposta = contar(7)
}
```

O programa gerado executa chamadas, quadro de pilha de cada funcao,
variaveis locais, `se`, `enquanto` e `retorne`, inclusive retornos
antecipados dentro de blocos. O quadro reserva 8 bytes por parametro e
variavel local; chamadas usam a convencao **interna** de argumentos
na pilha e retorno em `rax`, com `leave; ret`.

## Regras do subconjunto

- Funcoes declaradas antes de `inicio`, retorno e parametros `inteiro`;
  ate 16 funcoes, quatro parametros por funcao e 128 variaveis locais.
- Declaracoes `seja` somente no nivel exterior do corpo da funcao ou do
  `inicio`; variaveis de parametros e locais compartilham o mesmo escopo,
  sem nomes duplicados e sem sombra.
- Atribuicoes, comparacoes inteiras, aritmetica `+ - * / %`, `se`,
  `enquanto`, com ate 32 niveis de controle e retorno antecipado.
- **Analise dos caminhos de retorno:** cada funcao exige um
  `retorne expressao` final e incondicional no nivel exterior do corpo.
  A falta dessa garantia e o **erro 11**, com indice da posicao no
  fonte. Retornos antecipados dentro de `se` e `enquanto` sao
  permitidos, mas nao garantem sozinhos o retorno da funcao:
  um condicional pode ser falso e um laco pode nao executar.
- **Codigo inalcancavel:** qualquer nova instrucao apos `retorne` no
  mesmo bloco e rejeitada com **erro 10**, apontando o primeiro
  comando inalcancavel. Fechar o bloco restaura a analise do fluxo
  externo: comandos depois de um `se` ou `enquanto` com retorno
  interno continuam validos quando o ramo pode nao ser executado.
  O diagnostico e conservador e nao avalia a verdade das condicoes.
- Chamadas diretas permitidas no lado direito completo de declaracao,
  atribuicao e `retorne`, inclusive chamadas aninhadas como argumento
  integral: `retorne soma(dobro(n), soma(2, 3))`.
- **Validacao semantica de chamadas:** o emissor consulta a assinatura
  da funcao antes de gerar `call rel32` e diferencia quatro erros:
  **12** (nome de funcao desconhecido), **13** (quantidade de argumentos
  diferente da declaracao, incluindo funcoes sem parametros),
  **14** (chamada recursiva ou a funcao declarada mais adiante) e
  **15** (lista de argumentos malformada, como virgulas vazias).
  Os erros incluem o indice do token da chamada ou delimitador e
  nenhum arquivo ELF e gerado. A validacao percorre chamadas aninhadas.
- **Tipos:** a analise das assinaturas exige `inteiro` no retorno
  e em todos os parametros (erro **2** para outros tipos). As
  expressoes de argumentos usam a validacao do emissor de inteiros;
  tipos diferentes ainda nao sao suportados pelo subconjunto.
  Portanto, isto **nao** constitui inferencia geral de tipos.
- Cada argumento admite uma expressao aritmetica, uma chamada ou
  combinacoes como `soma(dobro(n) + 1, 4)` e `dobro(n) * 2 - 1`.
  O emissor preserva precedencia entre `+`, `-`, `*`, `/` e `%`, parenteses
  de agrupamento e sinais unarios. Emissoes com chamadas e operadores
  sao separadas recursivamente; chamadas puramente aritmeticas mantem o
  analisador de expressoes existente.
- Ate oito niveis de composicao recursiva (incluindo chamadas, grupos e
  operacoes). O emissor rejeita chamadas malformadas, recursivas ou
  futuras. Chamadas sao permitidas nos dois lados das comparacoes
  dos predicados `se`/`enquanto`, incluindo aritmetica mista.
  Expressoes de valor booleano e operadores logicos compostos ainda
  nao sao suportados.
- **Analise antecipada de divisao por zero:** o compilador recusa
  `/` e `%` cujo divisor seja uma constante comprovadamente zero,
  incluindo parenteses, sinais e pequenas expressoes aritmeticas
  como `7 / (5 - 5)` e `f(3) % (10 / 20)`. Usa **codigo 9** e
  informa o indice do operador no fonte; nenhum ELF e gerado nesses
  casos. O avaliador e conservador: so propaga constantes no intervalo
  de -1000000000 a 1000000000, sem nomes nem chamadas dinamicas.
  Isso nao e uma avaliacao de todas as constantes possiveis nem
  substitui a verificacao em tempo de execucao de divisores dinamicos.
- Para impedir recursao nesta etapa, uma funcao somente pode chamar
  funcoes **declaradas anteriormente**; chamadas futuras, recursivas e
  ciclos entre funcoes sao rejeitados.
- Nao implementa `senao`, booleanos compostos, tipos nao inteiros,
  `pare`, `continue`, ABI System V, funcoes aninhadas, chamadas
  externas, protecao de overflow aritmetico ou otimizacao especifica
  deste emissor. A divisao signed64 trunca para zero e o resto conserva
  o sinal do dividendo. Antes de `idiv`, o emissor faz verificacoes
  nativas de dois erros aritmeticos: divisor zero encerra o processo
  com status **240** e escreve `RS: divisao por zero (linha L, coluna C)`
  no **stderr**; dividendo minimo signed64 com divisor -1 encerra com
  status **241** e escreve `RS: estouro na divisao (linha L, coluna C)`.
  Os valores L e C sao calculados pela analise dos bytes do arquivo-fonte,
  com indices iniciados em 1 e a coluna contando bytes (nao caracteres
  Unicode). O apontamento refere-se ao operador `/` ou `%` da
  expressao responsavel pela falha, mesmo dentro de uma funcao ou
  de uma condicao. As mensagens sao emitidas pelo proprio ELF via
  `write(2,...)` do Linux, sem runtime externo; assim, um resultado
  valido de `inicio` que coincida com 240/241 nao produz stderr.
  Ainda **nao** sao excecoes recuperaveis e nao exibem a linha de
  codigo original. `inicio` continua expondo a ultima atribuicao
  como status de saida (modulo 256).

## Arquitetura

`instrucoes_integradas_elf.rts` acrescenta `analisar_corpo` ao
analisador de instrucoes: preserva uma unica IR com classe 7 para
`retorne`, faixas de tokens e profundidade de cada instrucao. O novo
`emissao_corpos_funcoes_elf.rts` compartilha o percurso dessa IR entre
o bloco principal e as funcoes. Os saltos `jcc/jmp` e os destinos
`call rel32` sao corrigidos em offsets absolutos no vetor de bytes.

## Testes

```text
python -m unittest testes.test_emissao_corpos_funcoes_elf_rs -v
```

A suite compila o emissor para Linux e Windows nos niveis O0 e O8,
valida a imagem ELF, executa programas no Linux e compara resultados
de funcoes com lacos e retornos antecipados. Casos invalidos devem
falhar sem gerar arquivo. A CI geral e obrigatoria antes da integracao.

## Proximo passo

Ampliar a analise de tipos alem de `inteiro` com representacao
tipada para argumentos e retorno, e posteriormente permitir chamadas
a funcoes declaradas mais adiante com analise de ciclos real.
Consolidar o fluxo com `senao`, evoluir falhas dinamicas para
erros recuperaveis e reduzir a dependencia do bootstrap Python.
