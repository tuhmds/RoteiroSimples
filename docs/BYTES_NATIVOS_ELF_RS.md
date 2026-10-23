# Primeiro suporte nativo de `bytes` no emissor ELF64 escrito em RS

O modulo `emissao_bytes_elf.rts` implementa **buffers locais imutaveis**
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

Cada declaracao `bytes` ocupa **40 bytes** na pilha:
8 bytes para o comprimento e 32 bytes reservados para o conteudo.
O inicializador aceita uma string literal de ate 32 bytes de UTF-8,
inclusive vazia. A contagem e em **bytes**, nao pontos de codigo Unicode.

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
- Inicializador obrigatoriamente string literal, sem escapes. Literal
  mais longo ou expressao de outro tipo: diagnostico **17**.
- `bytes` nao aceita reatribuicao neste momento: diagnostico **18**.
- Nao ha ainda mutacao por indice, leitura de arquivos para um local
  `bytes`, copia de buffers, passagem de `bytes` para funcoes nem
  retorno de `bytes`. As assinaturas continuam inteiras.
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
