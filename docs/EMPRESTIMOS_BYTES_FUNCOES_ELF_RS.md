# Parametros emprestados de bytes no emissor ELF64 escrito em RS

Este incremento adiciona o primeiro emprestimo **somente de leitura**
de buffers dinamicos entre funcoes no emissor nativo experimental
(`emissao_corpos_funcoes_elf.rts`).

## Exemplo

```rs
funcao primeiro(dados: emprestimo[bytes]) -> inteiro {
    retorne dados[0] + tamanho(dados)
}

inicio {
    seja dados: bytes = criar_bytes(100)
    dados[0] = 20
    seja resultado = primeiro(dados)
    dados[0] = 30
}
```

O argumento `dados` continua pertencendo ao chamador. A funcao
`primeiro` recebe somente o endereco de seu descritor, sem criar
um segundo buffer nem copiar os 100 bytes. Ao retornar, o chamador
ainda pode escrever, ler e desalocar o buffer.

## Contrato e ABI interna

Assinaturas aceitam `inteiro` ou `emprestimo[bytes]` como parametro,
ate o limite existente de quatro parametros por funcao. Retornos
continuam obrigatoriamente `inteiro`.

O argumento emprestado usa um slot de 8 bytes na ABI interna: ponteiro
para o slot do descritor do proprietario. O descritor do buffer
dinamico guarda ponteiro para memoria, comprimento e capacidade em
slots adjacentes. O emissor da funcao chamada recupera o comprimento
e os dados pelo descritor emprestado. Esse parametro tem classe de
tipo interna **4**, distinta do buffer dinamico proprietario
(classe **3**). O limpeza automatica libera apenas proprietarios
e nunca referencias emprestadas.

Um parametro emprestado pode ser passado adiante para outra funcao
que tambem espera `emprestimo[bytes]`. A cadeia de chamadas continua
sincrona e nao oferece armazenamento de referencias fora da funcao.

## Restricoes verificadas

- Somente um identificador de buffer dinamico proprietario ou de
  outro parametro emprestado pode ser argumento do emprestimo.
- Buffer de literal local (32 bytes), variavel inteira ou expressao
  temporaria nao pode ser passado como emprestimo neste incremento.
- A funcao emprestada pode chamar `tamanho(dados)` e
  ler `dados[indice]` com os mesmos limites seguros (saida 23).
- A funcao emprestada nao pode escrever `dados[indice] = ...`,
  usar `liberar_bytes(dados)` ou reatribuir `dados` inteiro.
- A referencia emprestada nao pode ser retornada como `inteiro`,
  nem ser implicitamente tratada como numero.
- `liberar_bytes(dados)` no proprietario invalida o descritor;
  um acesso posterior a um byte por referencia devolve saida 23
  na verificacao do comprimento zero.

O diagnostico 18 cobre incompatibilidades de tipo/emprestimo.

## Limitacoes atuais

Este e **um primeiro emprestimo read-only de curta duracao**, e nao
ownership completo. Ainda nao aceita transferencia de propriedade
para outra funcao, retorno de buffers, referencia armazenada em
registro, emprestimo estatico de literal local, alias mutavel, ou
comprovacao geral de ciclos de vida entre referencias.

Os testes cobrem chamadas diretas, encadeadas e com parametros mistos,
preservacao de propriedade pelo chamador, erros de tipagem e leitura
apos liberacao. Continuam sendo gerados arquivos ELF64 Linux x86-64;
o emissor escrito em RS ainda e compilado pelo bootstrap atual.
