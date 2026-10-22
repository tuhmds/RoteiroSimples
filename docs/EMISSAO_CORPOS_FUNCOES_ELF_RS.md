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
- Atribuicoes, comparacoes inteiras, aritmetica `+ - *`, `se`,
  `enquanto`, com ate 32 niveis de controle e retorno antecipado.
- **Obrigatorio um `retorne expressao` final no nivel exterior de cada
  funcao**, garantindo que a execucao nao termine por um caminho sem
  retorno. Outros retornos dentro de `se` e `enquanto` sao permitidos.
- Chamadas diretas permitidas no lado direito completo de declaracao,
  atribuicao e `retorne`, inclusive chamadas aninhadas como argumento
  integral: `retorne soma(dobro(n), soma(2, 3))`.
- Cada argumento admite uma expressao aritmetica, uma chamada ou
  combinacoes como `soma(dobro(n) + 1, 4)` e `dobro(n) * 2 - 1`.
  O emissor preserva precedencia entre `+`, `-` e `*`, parenteses
  de agrupamento e sinais unarios. Emissoes com chamadas e operadores
  sao separadas recursivamente; chamadas puramente aritmeticas mantem o
  analisador de expressoes existente.
- Ate oito niveis de composicao recursiva (incluindo chamadas, grupos e
  operacoes). O emissor rejeita chamadas malformadas, recursivas ou
  futuras. Divisao, resto, comparacoes em expressoes de valor e chamadas
  em predicados `se`/`enquanto` ainda nao sao suportados.
- Para impedir recursao nesta etapa, uma funcao somente pode chamar
  funcoes **declaradas anteriormente**; chamadas futuras, recursivas e
  ciclos entre funcoes sao rejeitados.
- Nao implementa `senao`, booleanos compostos, tipos nao inteiros,
  `pare`, `continue`, ABI System V, funcoes aninhadas, chamadas
  externas, protecao de overflow aritmetico ou otimizacao especifica
  deste emissor. `inicio` continua expondo a ultima atribuicao
  executada como status de saida do processo (modulo 256).

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

Expandir a representacao intermediaria para chamadas em predicados,
divisao e resto com verificacoes de erro, e fortalecer analise semantica
de saidas e tipos. Depois estudar recursao controlada, ABI publica e
etapas de bootstrap completo do compilador.
