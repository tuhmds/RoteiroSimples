# ELF64 em RS: primeiro programa com variaveis

Marco seguinte ao emissor de expressao da PR #42. A RS agora utiliza
`padrao/programa_compilador.rts` para resolver nomes de declaracoes e
gerar **instrucoes x86-64 para um programa pequeno**, sem executar a
expressao no momento da compilacao.

## Subconjunto da linguagem aceito

Somente um bloco principal com declaracoes de inteiros **inicializadas**,
na forma:

```text
inicio {
    seja quantidade = 10
    seja dobro = quantidade * 2
    seja total = dobro + (quantidade - 3)
}
```

Cada declaracao e expressao ficam em **uma mesma linha**; instrucoes podem
ser separadas por `;`. Os identificadores podem referenciar apenas valores
ja declarados. Sao aceitos literais 0..1000000000, `+`, `-`, `*`, sinais
unarios e parenteses. O executavel usa o valor da **ultima declaracao**
como codigo de saida Linux (modulo 256); este contrato experimental e
explicitamente diferente da semantica de programas RS completos.

O compilador analisa o texto inteiro e rejeita qualquer instrucao nao
suportada, inclusive funcoes, `se`, `enquanto`, atribuicoes posteriores,
chamadas, varios blocos `inicio`, `/`, `%`, declaracoes sem inicializador
ou tipagem explicita. Nao ignora codigo silenciosamente.

A ferramenta `exemplos/ferramentas/compilador_programa_elf_rs.rts`
le `codigo_fonte.rts` e grava `resultado_programa_elf` no diretorio
corrente.

## Como funciona

- AST e referencias: `padrao/programa_compilador.rts`.
- Um slot de pilha x86-64, de 8 bytes, por declaracao, no quadro `rbp`.
- Valores constantes: `mov rax, imm64`; leituras `mov rax, [rbp-disp32]`;
  gravacoes `mov [rbp-disp32], rax`.
- Aritmetica: `neg`, `add`, `sub`, `imul`, usando `push/pop`
  para avaliar a AST em pos-ordem.
- Saida: syscall Linux 60 (`exit`) com o ultimo valor no registrador
  `rdi`. Binario ELF64 estatico, sem interpretador dinamico.

A serializacao e a embalagem ELF reutilizam as funcoes RS ja validadas
em `emissao_elf_minima.rts`; nao ha nova dependencia obrigatoria de
Python, C, LLVM ou montador na **etapa de emissao**.

## Testes

```text
python -m unittest testes.test_emissao_programa_elf_rs -v
```

A CI compila a ferramenta para Windows e Linux nos niveis O0 e O8,
inspeciona os campos ELF e executa o resultado em Linux, comparando
o status com contas independentes, alem de casos de rejeicao.

## Limites

Este marco nao compila programas genericos. Ainda falta incorporar
atribuicoes, retorno de funcoes, controle de fluxo, dados, pilha ABI
completa e verificacoes de transbordamento. O compilador Python
atual continua necessario para construir a **ferramenta emissora**,
mas a propria ferramenta cria o ELF com rotinas RS.
