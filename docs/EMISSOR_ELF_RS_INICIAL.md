# Primeiro emissor ELF x86-64 escrito em RoteiroSimples

Marco experimental da transicao do compilador Python para a RS. O novo
`padrao/emissao_elf_minima.rts` consome a AST de `padrao/expressoes_compilador.rts`
e gera bytes de um executavel **ELF64 Linux x86-64**, diretamente na RS.

## Escopo do contrato

A ferramenta `exemplos/ferramentas/compilador_elf_inicial_rs.rts` recebe um
arquivo `expressao.rts` contendo **somente uma expressao** formada por
inteiros decimais nao negativos ate 1000000000, `+ - *`, unarios `+ -` e
parenteses. O resultado e `resultado_elf`, um ELF64 executavel Linux.
O proprio programa gerado avalia a expressao na CPU e chama a syscall
Linux `exit` (60). Seu codigo de saida corresponde aos **8 bits baixos**
do valor inteiro calculado; nao imprime o resultado.

Exemplo:

```text
2 + 3 * (4 + 1)
```

O programa emitido termina com status 17.

O ELF possui um segmento PT_LOAD (leitura e execucao), base 0x400000,
entrada em 0x400078, sem interpretador dinamico, relocacoes ou bibliotecas.
As instrucoes geradas sao `mov rax, im64`, `push/pop`, `neg`,
`add/sub/imul` e `syscall`.

Esse marco **nao** traduz um arquivo `.rts` com `inicio`, declaracoes,
funcoes ou chamadas para ELF e **nao e autocompilacao**. Identificadores,
`/`, `%`, outros tipos ou construcoes geram diagnostico; valores alem do
limite atual nao sao truncados silenciosamente. O estagio seguinte devera
usar `programa_compilador.rts` e suportar armazenamento de variaveis,
controle de fluxo, funcoes e emissao completa.

## Como reproduzir

O compilador Python atual e usado **somente** para construir a ferramenta
nativa RS. A ferramenta produz o ELF por conta propria, sem Python, C,
LLVM ou montador na etapa de emissao.

Execute na raiz do projeto:

```text
python -m unittest testes.test_emissao_elf_minima_rs -v
```

Os testes compilam a ferramenta RS em O0/O8 para Linux e Windows,
conferem os campos do ELF gerado em ambos e executam os arquivos
resultantes em Linux x86-64, comparando os codigos de saida com um
oraculo independente de expressoes simples. A versao Windows da
ferramenta **gera ELF**, mas nao tenta executar um ELF no Windows.

### Diagnosticos (codigo impresso pela ferramenta)

- 0: compilacao e gravacao solicitada;
- 1: erro de sintaxe/leitura da expressao;
- 2: identificador nao suportado;
- 3: operador ainda nao suportado;
- 4: literal fora do limite;
- 5: AST inconsistente com a pilha;
- 6: categoria de AST desconhecida;
- 7: expressao acima de 30000 nos.

A gravacao usa `grave_arquivo` da RS. Erros reais de abertura/gravar
arquivo dependem das regras da biblioteca de arquivos; o emissor nao
promete gravacao atomica nessa primeira etapa.
