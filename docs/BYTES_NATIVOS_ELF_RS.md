# Primeiro suporte nativo de `bytes` no emissor ELF64 escrito em RS

O modulo `emissao_bytes_elf.rts` implementa **buffers locais de capacidade fixa**
de `bytes` dentro do emissor experimental
`emissao_corpos_funcoes_elf.rts`.

```rs
funcao soma() -> inteiro {
    seja dados: bytes = "ABC"
    retorne dados[0] + dados[2] + tamanho(dados)
}
inicio {
    seja resultado = soma()
}
```

O exemplo retorna 135: os bytes ASCII 65 + 67 + comprimento 3.

## Representacao nativa

Cada declaracao `bytes` ocupa **56 bytes** na pilha neste emissor:
8 bytes para o comprimento, 32 bytes reservados para o conteudo e
16 bytes de descritor para emprestimos sem copia.
O inicializador aceita uma string literal com ate 32 bytes **decodificados** de UTF-8,
inclusive vazia. A contagem e em **bytes**, nao pontos de codigo Unicode.
O tamanho bruto do literal pode ser maior quando possui escapes.

O emissor x86-64 utiliza diretamente `mov byte [rbp+disp32], imm8`
para construir o buffer e `movzx eax, byte [rbp+rax+disp32]` para
ler um byte como inteiro positivo de 0 a 255. Nao e um objeto
Python, nem um vetor alocado pelo runtime externo.

`dados[indice]` aceita indice calculado por expressao inteira,
inclusive variaveis e argumentos de funcoes. Um indice negativo ou
igual/maior que o comprimento executa `exit(23)`: nao le memoria
fora dos 32 bytes reservados nem retorna valor arbitrario.

`tamanho(dados)` retorna o numero de bytes usados. A memoria do buffer
pertence ao quadro da funcao, portanto nao pode escapar do escopo.

## Limites intencionais deste primeiro incremento

- Tamanho maximo **32 bytes** por declaracao.
- Inicializador obrigatoriamente string literal. Escapes JSON ASCII
  aceitos: `\\n`, `\\r`, `\\t`, `\\b`, `\\f`, `\\\\`, `\\"` e `\\/`.
  Escapes Unicode `\\uXXXX`, incluindo pares substitutos UTF-16
  validos, tambem sao aceitos. Escapes incompletos, hexadecimais
  invalidos e substitutos isolados recebem diagnostico **17**, assim
  como literais que produzam mais de 32 bytes.
- `bytes` nao aceita reatribuicao neste momento: diagnostico **18**.
- A mutacao por indice pertence ao proprietario e preserva o limite
  verificado; nao se permite reatribuir o buffer inteiro. Nao ha
  retorno `bytes` nem emprestimos mutaveis ou com vida alem da chamada.
  Funcoes aceitam `inteiro` e `emprestimo[bytes]` (ate oito parametros
  neste emissor experimental). Leitura de arquivos diretamente para
  locais fixos e retorno de buffers continuam fora deste subconjunto.
- O emissor legado `emissao_integrada_elf.rts` rejeita explicitamente
  este tipo, para nao produzir codigo de maquina com layout errado.
- O bytecode ELF64 so e executavel em Linux x86-64. O compilador
  construido pelo bootstrap RS/Python roda tambem nos testes Windows.

## Validacao

```sh
python -m unittest testes.test_emissao_corpos_funcoes_elf_rs -v
python -m unittest testes.test_emissao_integrada_elf_rs -v
python -m unittest discover -s testes -v
```

Testes O0/O8 cobrem inicializacao, multiplas leituras, UTF-8, casos
dentro de `se`/`enquanto`, calculos em indices, acessos invalidos,
diagnosticos e compatibilidade com programas existentes.

Este incremento habilita manipulacao **limitada** de `bytes` em
codigo de maquina gerado por um modulo escrito em RS. **Nao
significa autocompilacao:** listas, registros completos, strings
dinamicas, ownership de buffers e o bootstrap independente continuam
pendentes.

## Decodificacao de escapes no emissor escrito em RS

A rotina `biblioteca_padrao/emissao_bytes_elf.rts` valida primeiro todo
o literal, calcula seu comprimento depois da decodificacao e so entao
emite as instrucoes x86-64 que gravam os bytes fixos. Por exemplo,
`"A\\nB"` usa 3 bytes, incluindo um LF (valor 10), mesmo que o
fonte contenha 4 caracteres entre aspas.

O modulo `biblioteca_padrao/literais_bytes_unicode_elf.rts` agora
interpreta `\\uXXXX`, combina pares UTF-16 validos para escalares
Unicode e gera 1 a 4 bytes UTF-8. Aceita `\\u0000` e rejeita pares
incompletos, substitutos solitarios e valores hexadecimais invalidos
com diagnostico **17**. Caracteres UTF-8 escritos diretamente
continuam conservados byte a byte. O limite permanece 32 bytes
**apos** a decodificacao, e emprestimos continuam sem copia.

Validacao: `python -m unittest testes.test_escapes_bytes_fixos_elf_rs -v`,
seguida da suite completa.

Validacao Unicode: `python -m unittest testes.test_unicode_escapes_bytes_elf_rs -v`,
seguida da suite completa O0/O8 para Windows e Linux.
