# Limpeza automatica de buffers dinamicos em escopos RS / ELF64

O emissor experimental `emissao_corpos_funcoes_elf.rts`, **escrito em
RoteiroSimples**, passa a emitir desalocacao automatica dos buffers
criados por `seja dados: bytes = criar_bytes(n)`.

## Semantica

O buffer pertence ao escopo lexico que o declarou. Ao abandonar esse
escopo, o executavel chama `munmap` **uma vez** se o ponteiro ainda
estiver ativo. A limpeza opera em ordem inversa a declaracao (LIFO)
e so considera variaveis do tipo dinamico ainda visiveis.

Os caminhos cobertos:

- Fechamento normal do bloco `se`, `senao` ou `enquanto`.
- Transicao `se ... senao`, antes de saltar o segundo ramo.
- `continue`: libera os recursos do laco e seus blocos internos
  antes de voltar ao predicado.
- `pare`: libera os recursos do laco e de seus blocos internos
  antes de abandonar o laco, preservando donos externos.
- `retorne`: libera os donos locais e dos blocos aninhados sem
  alterar o valor inteiro retornado em `rax`.
- Fechamento de `inicio`: libera buffers locais ainda ativos sem
  alterar o codigo inteiro de saida em `rdi`.

## Exemplo

```rs
funcao processar() -> inteiro {
    seja dados: bytes = criar_bytes(128)
    dados[0] = 81
    retorne dados[0]
}

inicio {
    seja resultado = processar()
}
```

**Nao e mais necessario chamar `liberar_bytes(dados)` antes de
`retorne`**. Uma liberacao explicita continua valida, inclusive
para diminuir o tempo de vida de uma alocacao antes do fim do escopo.
Como `liberar_bytes` invalida o ponteiro, a limpeza automatica
verifica se o descritor ainda esta ativo e ignora o recurso liberado.
Duas liberacoes explicitas permanecem invalidas (saida 25).

## Implementacao

O modulo `emissao_bytes_elf.rts` emite uma verificacao do ponteiro
e reutiliza a rotina existente de `munmap`. A rotina automatica
preserva `rax` e `rdi`. O emissor de corpos mantem a lista de nomes
visiveis, os tipos locais, os marcadores de escopos e o marcador do
`enquanto` mais interno para limpar apenas recursos relevantes.

Os slots de pilha continuam estaveis. Os nomes de ramos ja fechados
sao marcados como inativos e nao sao novamente desalocados.

## Validacao

A suite `testes/test_emissao_corpos_funcoes_elf_rs.py` cobre
fechamento de escopo, ambos os ramos condicionais, retorno antecipado,
liberacao explicita anterior, preservacao do retorno, `pare` e
`continue`. Em Linux x86-64, testes adicionais executam centenas de
alocacoes de 1 MiB sob limite virtual `RLIMIT_AS` de 96 MiB. A
ausencia de limpeza causaria falha de `mmap` (saida 24); a limpeza
deve permitir a conclusao do programa.

## Limites e riscos restantes

Este mecanismo nao constitui um coletor de lixo nem prova
de seguranca completa de memoria. Nao cobre encerramento anormal por
falhas de limites, alocacao ou syscall, e ainda nao oferece
passagem de buffers entre funcoes, retorno de bytes, referencias ou
aliasing. No encerramento do processo Linux, os mapeamentos restantes
sao recuperados pelo sistema operacional.

A compilacao do emissor escrito em RS ainda usa bootstrap Python.
