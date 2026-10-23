# Bytes mutaveis e buffers dinamicos no emissor ELF escrito em RS

Este incremento amplia o emissor experimental ELF64 Linux x86-64, escrito em RoteiroSimples, com escrita por indice e armazenamento dinamico. O bootstrap Python ainda e utilizado para construir o emissor RS.

## Exemplo

```rs
funcao exemplo() -> inteiro {
    seja dados: bytes = criar_bytes(128)
    dados[120] = 201
    seja resultado = dados[120] + tamanho(dados)
    liberar_bytes(dados)
    retorne resultado
}
inicio { seja codigo = exemplo() }
```

- `seja dados: bytes = "ABC"` conserva os 32 bytes de armazenamento local em pilha.
- `dados[indice] = valor` escreve em buffers locais e dinamicos.
- `seja dados: bytes = criar_bytes(comprimento)` aloca memoria anonima e zerada via syscall Linux `mmap`. O comprimento pode ser expressao inteira.
- `tamanho(dados)` retorna comprimento logico.
- `dados[indice]` devolve um inteiro no intervalo 0..255.
- `liberar_bytes(dados)` executa `munmap` e invalida o descritor.

## Representacao e limites

Buffers locais antigos continuam com 40 bytes de pilha: comprimento (8 bytes) e dados (32 bytes).

Buffers dinamicos usam cinco slots de pilha para estabilidade do emissor, sendo tres utilizados: ponteiro do `mmap`, comprimento logico e capacidade alocada. A capacidade e comprimento+1 (permite buffer logico vazio). O teto deste incremento experimental e **1 MiB**.

Leituras e escritas validam indice negativo e indice maior/igual ao comprimento. Escrita tambem rejeita valor negativo e maior que 255, sem truncamento silencioso.

Codigos de saida: **23** para indice/valor invalido e leitura de buffer liberado; **24** para tamanho invalido/maior que o limite ou falha de `mmap`; **25** para liberacao dupla ou falha do `munmap`.

O erro de compilacao **18** rejeita atribuicao ao buffer inteiro, atribuicao indexada em inteiros e tentativa de liberar buffer estatico.

## Gerenciamento de memoria

**Atualizacao — limpeza automatica de escopos (PR #68):** no emissor `emissao_corpos_funcoes_elf.rts`, todo buffer dinamico ainda ativo e liberado automaticamente ao fim do seu escopo, em `retorne`, em `pare`, em `continue` e no encerramento de `inicio`. O fechamento normal de `se/senao` e `enquanto` tambem libera os buffers pertencentes a seus respectivos blocos. A limpeza preserva o valor retornado.

`liberar_bytes(dados)` permanece disponivel e invalida o descritor imediatamente. A limpeza automatica ignora um descritor ja liberado; duas liberacoes **explicitas** continuam resultando no codigo 25.

A liberacao automatica se restringe a **variaveis dinamicas locais**: ainda nao ha passagem/retorno de buffers entre funcoes, ownership estatico integral, desalocacao em encerramentos anormais por `exit(23/24/25)`, nem coletor de lixo. O processo Linux recupera seus mapeamentos apos saida anormal. Nao representa a autocompilacao integral. Veja `docs/BYTES_LIMPEZA_AUTOMATICA_ELF_RS.md`.

## Validacao

A suite `testes/test_emissao_corpos_funcoes_elf_rs.py` cobre escrita e leitura O0/O8, buffer vazio, 1 MiB, indices calculados, liberacao, reuso invalido, escopos e loops em Linux x86-64. A matriz CI executa os testes de compilacao em Windows e Linux, com Python 3.10/3.11/3.14. O emissor ELF legado continua recusando bytes dinamicos.
