# Plano de instrucoes e emissor ELF integrado em RoteiroSimples

Esta etapa integra em **um unico caminho de emissao** capacidades
anteriormente implementadas separadamente: chamadas `call/ret`,
variaveis locais, `se`, `enquanto`, comparacoes e atribuicoes.

## Pipeline

1. `padrao/lexico.rts` reconhece tokens.
2. `padrao/assinaturas_compilador.rts` identifica funcoes.
3. `padrao/instrucoes_integradas_elf.rts` produz uma **lista tipada
   e ordenada de instrucoes** para o bloco `inicio`, com classes de
   declaracao, atribuicao, condicional, repeticao e fechamento de bloco,
   preservando faixas de tokens e profundidade.
4. `padrao/emissao_integrada_elf.rts` percorre essas instrucoes,
   utiliza o emissor de expressoes/condicoes ja existente, emite
   chamadas e corrige os saltos relativos.
5. `padrao/emissao_elf_minima.rts` escreve a imagem ELF64.
6. A ferramenta `exemplos/ferramentas/compilador_integrado_elf_rs.rts`,
   **compilada pelo bootstrap Python**, recebe `codigo_fonte.rts`
   e grava `resultado_integrado_elf`.

## Exemplo

```text
funcao dobro(x: inteiro) -> inteiro {
    retorne x * 2
}

inicio {
    seja contador = 0
    seja total = 0
    enquanto contador < 4 {
        contador = contador + 1
        se contador >= 2 {
            total = dobro(total + contador)
        }
    }
}
```

O ELF gerado executa `dobro` dentro do bloco condicional e do laco.
O status de saida resulta em 36.

## Escopo e limites

- Funcoes declaradas antes de `inicio`, com 0 a 4 parametros
  inteiros, corpo `retorne expr` aritmetica e no maximo 16 funcoes.
- `inicio` com no maximo 128 locais, declarados apenas no escopo
  externo e sempre inicializados.
- Atribuicoes a locais anteriores dentro e fora de blocos de controle.
- `se` e `enquanto` com comparacoes inteiras; aninhamento maximo 32.
- Chamada direta de funcao no **lado direito inteiro** de uma
  declaracao ou atribuicao. Argumentos podem ter aritmetica e locais.
- `senao`, chamadas aninhadas, recursao, funcoes contendo lacos,
  parametros que nao sejam inteiros, tipos compostos, chamadas
  externas, ABI System V e autocompilacao completa **nao** suportados.
- O codigo de saida do processo representa a ultima atribuicao
  executada modulo 256. Essa convencao e apenas da prova de conceito.
- O plano IR cobre as instrucoes do `inicio`; os corpos das funcoes
  continuam submetidos ao subconjunto `retorne expr` e ao parser
  aritmetico, nao a uma IR geral de funcoes.

## Testes

```text
python -m unittest testes.test_emissao_integrada_elf_rs -v
```

A suite gera a ferramenta nativa RS para Linux e Windows com
otimizacao O0 e O8, verifica cabecalhos ELF e instrucoes
`call`/`ret`/`jcc`/`jmp`, executa os binarios no Linux e compara
com resultados calculados separadamente. Entradas invalidas devem
produzir erro sem gravar arquivo de saida.

### Proximo marco

Estender a IR para o interior das funcoes, com `retorne` em varios
caminhos, locais, recursao controlada, semantica de parametros e
convencao ABI definida; depois substituir o bootstrap Python.
