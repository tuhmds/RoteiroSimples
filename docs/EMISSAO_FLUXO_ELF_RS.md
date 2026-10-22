# Emissao ELF64 de desvios condicionais e lacos escrita em RS

O modulo \`padrao/emissao_fluxo_elf.rts\` estende a prova de emissao da
RoteiroSimples: agora o codigo gerado executa \`se\`, \`enquanto\` e atribuicoes
locais, com testes reais de CPU Linux x86-64.

## Subconjunto aceito

\`\`\`text
inicio {
    seja quantidade = 0
    seja soma = 0
    enquanto quantidade < 5 {
        quantidade = quantidade + 1
        se quantidade >= 3 {
            soma = soma + quantidade
        }
    }
}
\`\`\`

- Um unico \`inicio { ... }\`; declaracoes \`seja\` obrigatoriamente
  inicializadas e apenas no bloco principal; no maximo 128 variaveis.
- Atribuicoes a variaveis anteriores do mesmo bloco; nao ha declaracoes
  nem sombreamento dentro de \`se\` ou \`enquanto\`.
- Expressoes inteiras: literais 0..1000000000, nomes, \`+\`, \`-\`, \`*\`,
  sinais unarios e parenteses.
- Condicoes: \`<\`, \`<=\`, \`>\`, \`>=\`, \`==\`, \`!=\` comparando duas
  expressoes inteiras, com interpretacao signed64.
- \`se\` e \`enquanto\` com chaves obrigatorias, aninhados ate 32 niveis;
  **sem** \`senao\`, \`pare\`, \`continue\`, funcoes, escrita, leitura,
  outros tipos ou chamadas.
- Declaracoes e atribuicoes ocupam uma linha ou terminam em \`;\`.
- O valor observado e **a ultima atribuicao executada modulo 256**
  como status do processo Linux; este nao e o comportamento de todos os
  programas RS e nao substitui a semantica geral da linguagem.

## Emissao nativa

A ferramenta RS \`exemplos/ferramentas/compilador_fluxo_elf_rs.rts\`
le \`codigo_fonte.rts\` e grava \`resultado_fluxo_elf\`.

O backend usa \`padrao/lexico.rts\`, \`padrao/expressoes_compilador.rts\`
e reutiliza o cabecalho ELF e a emissao little-endian da PR #42.
Os locais ficam em enderecos \`[rbp-disp32]\`. \`cmp rax, rcx\`,
\`jcc rel32\` e \`jmp rel32\` implementam as condicoes e repeticoes.
Os saltos relativos sao preenchidos depois da geracao do bloco,
mantendo posicoes dentro do mesmo segmento ELF RX.

O emissor rejeita fonte fora do subconjunto em vez de descartar comandos
nao reconhecidos. Erros encontrados deixam de gerar o arquivo final.
A construcao da ferramenta ainda depende do bootstrap Python atual,
mas **a montagem do ELF acontece totalmente em RS**.

## Testes

\`\`\`text
python -m unittest testes.test_emissao_fluxo_elf_rs -v
\`\`\`

A CI compila a ferramenta para Windows e Linux, niveis O0 e O8. Confere
o ELF produzido nas duas plataformas e executa os programas Linux com
limite de tempo, comparando resultados com calculos independentes.

## Proxima etapa

Integrar uma AST de instrucoes geral com retorno, chamadas, parametros,
tipos e atribuicoes na analise semantica. A emissao de fluxo aqui e uma
prova incremental **restrita**, nao um compilador autocompilado.
