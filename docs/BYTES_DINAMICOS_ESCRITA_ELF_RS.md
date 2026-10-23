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

A liberacao e **explicita, nao automatica**. O programa deve executar `liberar_bytes` exatamente uma vez para cada buffer dinamico alocado com sucesso, inclusive antes de `retorne`, `pare`, `continue` e saidas de escopo. Omitir liberacao em loops ou funcoes de longa duracao causa vazamento ate o fim do processo.

Nao ha ainda passagem ou retorno de buffers dinamicos entre funcoes, atribuicao de buffers inteiros, ownership estatico completo, coletor de lixo ou desalocacao automatica de valores esquecidos. Nao representa a autocompilacao integral.

## Validacao

A suite `testes/test_emissao_corpos_funcoes_elf_rs.py` cobre escrita e leitura O0/O8, buffer vazio, 1 MiB, indices calculados, liberacao, reuso invalido, escopos e loops em Linux x86-64. A matriz CI executa os testes de compilacao em Windows e Linux, com Python 3.10/3.11/3.14. O emissor ELF legado continua recusando bytes dinamicos.
