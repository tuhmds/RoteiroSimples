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

- Somente um identificador de buffer fixo na pilha, dinamico proprietario
  ou outro parametro emprestado pode ser argumento do emprestimo.
- Variavel inteira e expressao temporaria nao podem ser passadas como
  emprestimo. A forma direta de texto literal como argumento tambem
  continua sem suporte; primeiro declare uma variavel `bytes`.
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
registro, emprestimo de literal temporario, alias mutavel, ou
comprovacao geral de ciclos de vida entre referencias.

Os testes cobrem chamadas diretas, encadeadas e com parametros mistos,
preservacao de propriedade pelo chamador, erros de tipagem e leitura
apos liberacao. Continuam sendo gerados arquivos ELF64 Linux x86-64;
o emissor escrito em RS ainda e compilado pelo bootstrap atual.

## Bytes fixos emprestados (incremento seguinte)

`seja dados: bytes = "ABC"` agora tambem pode ser argumento de
`funcao ler(dados: emprestimo[bytes]) -> inteiro`. O emissor reserva
**sete qwords de pilha** para cada buffer fixo: comprimento original,
32 bytes de dados e dois slots contiguos de descritor emprestavel
(ponteiro, comprimento). `emprestimo[bytes]` continua contendo o
endereco do slot de ponteiro; assim o destinatario usa a mesma ABI
read-only para buffers fixos, dinamicos e reemprestados.

Os dois slots extras pertencem ao quadro do chamador. A referencia
so e valida durante a chamada sincrona; nao pode ser retornada,
armazenada como referencia persistente, liberada, nem alterada na
funcao chamada. O proprietario ainda pode alterar o proprio buffer
apos o retorno, sem refazer o descritor, pois seu comprimento nao muda.
O limite de 32 bytes permanece para buffers fixos; para comprimentos
maiores use `criar_bytes`. Nao ha transferencia de propriedade nem
emprestimo de temporarios.

A regressao O0/O8 cobre texto ASCII, UTF-8, buffer vazio, leituras
fora de limites, reemprestimo encadeado, atualizacao do proprietario,
locais intercalados e escopos aninhados. O Python de bootstrap segue
necessario para compilar o emissor escrito em RS; esta etapa **nao**
representa autocompilacao integral.
