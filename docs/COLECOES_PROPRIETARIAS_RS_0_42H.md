# RS 0.42H — Coleções de registros proprietários

## Contrato

`lista[Registro]` agora aceita registros com folhas proprietárias: texto,
bytes, listas e subregistros. Campos de registros também podem ser listas
de registros previamente declarados, incluindo registros copiáveis.
A lista conserva seu descritor de três palavras e possui todos os elementos.

```text
tipo Documento {
    titulo: texto
    conteudo: bytes
}
inicio {
    seja documentos: lista[Documento]
    seja documento: Documento
    copie(documento.titulo, "Relatório")
    adicione_byte(documento.conteudo, 255)
    adicione(documentos, mova(documento))
    seja escolhido = retire(documentos, 0)
    escreva(escolhido.titulo)
    escreva(tamanho(documentos))
}
```

A saída é `Relatório` e `0`. O registro retirado passa a ter dono independente.

## Operações

| Operação | Propriedade e efeito |
|---|---|
| `adicione(colecao, mova(registro))` | Acrescenta o registro e inativa seus donos na origem |
| `adicione(colecao, criar())` | Consome o registro novo devolvido pela função |
| `colecao[indice] = mova(registro)` ou função nova | Descarta os campos antigos e recebe os novos donos |
| `retire(colecao, indice)` | Devolve o registro por transferência, remove a posição e conserva a ordem restante |
| `remova_ultimo(colecao)` | Descarta o último registro e reduz o tamanho |
| `limpe_lista(colecao)` | Descarta todos os elementos; conserva capacidade para reuso |
| `libere(colecao)` | Descarta os elementos e o armazenamento; inativa a lista |
| `mova(destino, origem)` | Descarta a lista antiga do destino e transfere o descritor completo |

Inserção e substituição exigem movimento ou um valor novo; não há cópia
implícita de donos. Todas as folhas de um registro são verificadas antes
de transferi-lo. Um registro parcialmente movido ou liberado é rejeitado
em execução, com o diagnóstico controlado de valor inativo.

`retire` produz um registro proprietário. Pode inicializar uma variável,
ser retornado por uma função ou passado diretamente a outra função,
inclusive a `sucesso[Registro]`. Também pode alimentar inserção ou substituição.
Os temporários intermediários têm os mesmos aliases de campos e descarte
da RS 0.42F. Índices são avaliados uma vez. Substituição verifica o índice
antes do valor e revalida a lista/índice depois de avaliar um valor que possa
ter efeitos, sem guardar um ponteiro do heap entre chamadas.

Listas passam entre funções por `mova` ou retorno novo, como outras listas
proprietárias. Registros que contêm essas listas também passam por funções
e podem ser conteúdo de resultados proprietários da RS 0.42G.

## Memória e descarte

A largura do elemento e os offsets de suas folhas vêm da disposição comum
dos tipos. Elementos são contíguos, com palavras crescentes no heap; registros
locais usam palavras decrescentes no quadro. Os adaptadores respeitam essas
duas orientações ao transportar descritores.

O crescimento continua no alocador compartilhado. Move o armazenamento da
lista sem copiar o conteúdo apontado pelos campos e sem destruir os elementos
ao liberar a área antiga. Após retirar um registro, o restante é deslocado
com palavras de 64 bits e a antiga última posição é zerada fora do tamanho.

Cinco auxiliares são emitidos por tipo de elemento utilizado: descarte do
elemento, limpeza, liberação, substituição e retirada. A limpeza comum passa
a selecionar o descarte apropriado ao tipo da lista em todos os caminhos,
incluindo parâmetros, temporários, campos de registros, retornos antecipados,
`continue`, `pare`, liberação explícita e substituição de listas inteiras.
Coleções aninhadas são descartadas por seus tipos, preservando dono único.

O grafo de tipos não admite ciclos nem mais de 32 níveis de coleções
proprietárias. O limite mantém pequena e previsível a pilha dos auxiliares
de descarte. A análise memoriza a profundidade de cada tipo, evitando trabalho
exponencial quando vários campos compartilham o mesmo tipo descendente.
O orçamento de 768 KiB das funções continua preservando margem para sistema
e auxiliares. Não foram acrescentados níveis de otimização ou outro alocador.

Falha de alocação permanece fatal e controlada; não há rollback recuperável
de inserção nesta revisão. A expansão não libera a área antiga antes de
obter a nova. Os executáveis continuam PE/ELF independentes de Python.

## Leitura e restrições

Ler `colecao[indice]` por cópia é rejeitado quando o registro contém donos.
Use `retire` para obter seu valor. Registros copiáveis mantêm leitura e
atribuição por valor, com o comportamento histórico das listas tipadas.

`emprestimo[lista[Registro]]` permite consultar tamanho/capacidade; não permite
copiar um elemento proprietário, retirar, inserir ou substituir elementos.
Ainda falta empréstimo de leitura de um registro dentro da coleção e acesso
direto a seus campos. Não há referência persistente para posições do heap.
Na mesma árvore de chamada, `retire` não pode compartilhar sua lista com um
movimento ou empréstimo explícito dessa lista. Para retirar a última posição,
`retire(colecao, tamanho(colecao) - 1)` é permitido.

`retire` desta revisão exige lista dona com elemento proprietário; não é
um novo operador de cópia para listas de escalares ou registros copiáveis.
Listas de donos simples como `lista[texto]`, tipos recursivos, resultados
diretos de listas e empréstimos mutáveis permanecem fora deste marco.

## Exemplo e verificação

O exemplo `exemplos/aplicacoes/colecao_documentos_rs042h.rts` usa a biblioteca
`padrao/documentos.rts` da RS 0.42G, constrói um catálogo, retira e substitui
documentos, reutiliza a capacidade e descarta uma coleção de catálogos.

```text
python -m unittest testes.test_colecoes_proprietarias_rs042h -v
python -m unittest testes.test_abi_colecoes_proprietarias_rs042h -v
python -m unittest discover -s testes -v
python compilar.py exemplos/aplicacoes/colecao_documentos_rs042h.rts --alvo windows -O 8 -o catalogo.exe
```

Para Linux, use `--alvo linux`. Os cenários centrais percorrem O0–O8 e os
demais O0/O8. Ambos os formatos são gerados, com execução do formato nativo
em cada sistema na CI. São testados 257 registros com três donos, ordem após
retiradas no começo/meio/fim, substituição, limpeza/reuso, coleções aninhadas,
resultados, empréstimos, saídas de escopo, índices inválidos, estado parcial,
consumo da lista durante o valor e limite de 32 níveis.

No Windows real, o hospedeiro verifica oito ponteiros de conteúdo preservados
em duas expansões, as liberações de registros substituídos/removidos e dezessete
ponteiros finais, incluindo o armazenamento da lista. Exercita movimento de
listas, limpeza, `continue`/`pare` e descarte aninhado: 45 alocações e 45
liberações. Também verifica oito registradores inteiros, dez vetoriais não
voláteis, RSP, estados de desenrolamento e exceções reais nos dez auxiliares
de dois tipos. Um ensaio separado nega a expansão da lista, confirma a saída
controlada e observa os quatro registros antigos intactos, sem liberação
antecipada. Esses ensaios Windows são ignorados no Linux.

Este marco amplia a base de coleções para bibliotecas, Dados RS, compilador
em RS e Studio. Não implementa um motor transacional ou interface gráfica.
