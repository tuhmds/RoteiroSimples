# RS 0.42A.3 — Dados binários dinâmicos

Marco posterior ao texto 0.42A.2, baseado no commit `78a0bc0`. A branch
`rs-0.42a-bytes-dinamicos` depende de `rs-0.42a-texto-dinamico`, que depende
do primeiro marco de propriedade. Nenhuma PR é mesclada automaticamente.

## Sintaxe implementada

```text
funcao criar() -> bytes {
    seja dados: bytes
    adicione_byte(dados, 0)
    adicione_byte(dados, 255)
    retorne mova(dados)
}
funcao consultar(dados: emprestimo[bytes]) -> inteiro {
    retorne dados[0] + tamanho(dados)
}
inicio {
    seja dados = criar()
    dados[0] = 128
    seja copia: bytes
    copie(copia, dados)
    junte(copia, dados)
    grave_arquivo("dados.bin", copia)
    limpe(dados)
    carregue_arquivo("dados.bin", dados)
    escreva(consultar(empreste(dados)))
}
```

| Operação | Semântica |
|---|---|
| `seja dados: bytes` | Dono vazio, comprimento/capacidade zero, sem alocação inicial |
| `adicione_byte(dados, valor)` | Acrescenta inteiro de 0 a 255; cresce se necessário |
| `dados[indice]` | Inteiro de 0 a 255; exige `0 <= indice < tamanho(dados)` |
| `dados[indice] = valor` | Substitui byte existente, sem aumentar comprimento |
| `tamanho(dados)`, `capacidade(dados)` | Quantidades em bytes; verificam dono vivo |
| `copie(destino, origem)` | Cópia profunda explícita; substitui conteúdo e preserva origem |
| `junte(destino, origem)` | Acrescenta conteúdo; origem pode ser o próprio destino |
| `limpe(dados)` | Zera comprimento, conservando armazenamento para reutilização |
| `mova(origem)` | Transfere para parâmetro, retorno ou declaração nova |
| `mova(destino, origem)` | Descarta conteúdo anterior e transfere descritor; pode reativar destino |
| `libere(dados)` | Descarta explicitamente; segundo descarte explícito falha |
| `empreste(dados)` | Referência temporária de leitura para parâmetro `emprestimo[bytes]` |
| `grave_arquivo("dados.bin", dados)` | Grava comprimento exato; aceita dono, empréstimo ou buffer fixo |
| `carregue_arquivo("dados.bin", dados)` | Substitui conteúdo, crescendo até EOF; empréstimo não é destino |

`bytes[N]` continua copiável como valor composto e conserva capacidade fixa.
Cópia/acréscimo explícitos entre buffers fixos e dinâmicos são permitidos;
excesso no destino fixo encerra com diagnóstico, sem truncamento. Literais
textuais, `caracteres`, `byte_em` e impressão textual não aceitam bytes.
Para consultar um byte binário use `dados[indice]`.

## Propriedade e memória

`compilador/propriedade.py` define ambos os novos tipos, capacidades e passo
de um byte. Donos usam as três palavras já compartilhadas: ponteiro,
comprimento e capacidade. Empréstimos usam uma referência ao descritor.
Estado inativo mantém comprimento -1 e ponteiro/capacidade zero.

O gerenciador `backend/memoria_dinamica.py` é o mesmo usado por listas e
texto: VirtualAlloc/VirtualFree no Windows e mmap/munmap no Linux.
Os nomes históricos `rs_lista_alocar` e `rs_lista_desalocar` são preservados.
Não existe alocador paralelo para bytes. O crescimento começa com quatro
unidades, dobra de forma verificada e usa o tamanho exato se dobrar
excederia o intervalo assinado. Multiplicação e soma de tamanhos verificam
estouro antes da alocação e do acesso ao conteúdo.

`backend/sequencias_dinamicas.py` centraliza vistas e cópia crescente.
`rs_texto_modificar` valida UTF-8 e chama `rs_sequencia_modificar`; bytes
chamam diretamente a rotina comum. O autoacréscimo recarrega o ponteiro da
fonte depois da reserva, evitando ler uma alocação antiga já liberada.
As três palavras são movimentadas entre funções sem alocação ou cópia
oculta. Donos locais e parâmetros consumidos são descartados por escopo,
inclusive em retornos antecipados, `pare` e `continue`.

Índice e valor podem conter chamadas com efeitos. O destino é verificado
depois das expressões, sem repeti-las, antes de obter o ponteiro atual.
Uma expressão que consome o próprio destino termina com diagnóstico de
movimentação/liberação e não acessa seu antigo armazenamento.

Empréstimos permanecem restritos a chamadas síncronas de leitura, podem
ser retransmitidos e não podem ser guardados, retornados ou modificados.
A árvore de chamada rejeita consumo duplicado e empréstimo/consumo do
mesmo dono. Cópia implícita e reatribuição de donos são rejeitadas.

## Arquivos e separação UTF-8/binário

A leitura crescente usa a rotina comum `rs_arquivo_carregar_dinamico`,
com indicação explícita do tipo no chamador. Texto exige validação UTF-8
ao concluir; bytes aceitam todos os 256 valores, incluindo NUL, codificações
incompletas, substitutos e sequências não textuais. Programas exclusivamente
binários não emitem o validador de texto.

Os blocos de transferência têm no máximo 1 MiB; esse limite não limita
o comprimento total. Leituras/escritas parciais são repetidas. No Linux,
EINTR é repetido. Antes de expandir um buffer completamente preenchido,
um byte de prova detecta EOF: arquivo vazio não aloca e EOF exatamente
na capacidade não duplica armazenamento. Releitura reutiliza a capacidade.

As políticas de caminho, inspeção de arquivo regular e rejeição de links
permanecem nas rotinas históricas. A gravação completa mantém a semântica
histórica de substituição de conteúdo; não é publicação atômica.

## Efeitos e geradores

| Nó | Memória/propriedade | Falha/efeito |
|---|---|---|
| `adicione_byte_dinamico` | Lê/escreve e altera dono | Valor, estado, crescimento/alocação |
| `atribua_byte_dinamico` | Lê/escreve e altera dono | Expressões, estado, índice e valor |
| `modifique_bytes` | Lê origem e destino, escreve destino | Estado, tamanho e memória/capacidade |
| `limpe_bytes_dinamicos` | Limpa dono | Estado |
| `tamanho_bytes_dinamicos`, `capacidade_bytes_dinamicos` | Leitura | Estado |
| `indice_bytes` | Leitura e efeitos da expressão do índice | Estado e limite |
| `empreste_bytes_dinamicos` | Leitura temporária do descritor | Estado |
| `carregue_bytes_dinamicos` | Preenche dono | Arquivo, estado e memória |

Movimentação e descarte reutilizam os nós comuns de propriedade. Os efeitos
observáveis conservam a ordem; o gerador conservador continua selecionado
de O0 a O8. A IR/SSA não passa a otimizar esses recursos nesta entrega.

Offsets e orçamento seguro de pilha das funções são preservados. A nova
rotina compartilhada e as rotinas de arquivo mantêm prólogos/epílogos
verificados, `.pdata` e `.xdata` no Windows. A API de desenrolamento real
verifica fronteiras de instruções, e exceções INT3 atravessam dois quadros.

## Biblioteca e aplicação em RS

`padrao/binarios.rts` oferece `duplicar`, `concatenar`, `iguais` e
`soma_verificacao`. As duas primeiras realizam cópia explícita; comparação
e soma usam empréstimos e indexação verificada. A soma modular de 16 bits
é somente demonstrativa, sem garantia criptográfica.

`exemplos/aplicacoes/arquivo_binario_rs042a.rts` constrói 8.195 bytes,
incluindo todos os valores, transfere entre funções, grava, recupera,
compara e demonstra que modificar uma cópia não altera o original.
O executável não depende de Python nem das bibliotecas do hospedeiro.

```text
python compilar.py exemplos/aplicacoes/arquivo_binario_rs042a.rts --alvo windows -O 8 -o arquivo_binario.exe
python compilar.py exemplos/aplicacoes/arquivo_binario_rs042a.rts --alvo linux -O 8 -o arquivo_binario
python -m unittest testes.test_bytes_dinamicos_parser_rs042a testes.test_bytes_dinamicos_nativo_rs042a testes.test_abi_bytes_dinamicos_rs042a -v
python -m unittest discover -s testes -v
```

## Verificação e limites

40 testes novos: 11 de tipagem/contratos, 26 de execução nativa portátil e
3 de ABI/desenrolamento Windows. Positivos executam O0–O8; falhas usam
O0/O4/O8 e injeções impossíveis pela sintaxe usam O0/O8. A suíte cobre
vazio, todos os bytes, dados gerados com semente 42003, expansão/reuso,
autoacréscimo, cópias independentes, arquivos acima de 1 MiB, transferências,
recursão, uso após movimentação/liberação, índices e valores inválidos,
overflow de comprimento e falha de alocação simulada no executável real.

O ensaio Windows observa 11 alocações e 11 liberações, preservação de oito
registradores inteiros, dez vetoriais e RSP, ponteiro idêntico durante
transferências sem alocar/liberar e descarte correto dos escopos.
Resultados finais da suíte e CI serão registrados depois da execução.

Permanecem pendentes donos dentro de registros/listas, empréstimos mutáveis,
fatiamento binário, igualdade direta pela sintaxe, operações posicionais
com buffers dinâmicos, caminhos dinâmicos nas APIs de arquivo completo,
tratamento recuperável de falhas, operadores lógicos e reais/decimais.
`HIGH_ENTROPY_VA` continua desativado. Este marco conclui o objetivo de bytes
dinâmicos; não conclui toda a missão RS 0.42 nem a autocompilação.
