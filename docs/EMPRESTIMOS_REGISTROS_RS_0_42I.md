# RS 0.42I — Leitura de registros por empréstimo

## Contrato e sintaxe

`emprestimo[Registro]` é um parâmetro temporário de leitura. Aceita registros
locais e elementos de listas dinâmicas, inclusive listas já emprestadas.
Não transfere a propriedade, não remove o elemento e não aloca seu conteúdo.

```text
tipo Documento {
    codigo: inteiro
    titulo: texto
    conteudo: bytes
}
funcao consultar(documento: emprestimo[Documento]) -> inteiro {
    escreva(documento.titulo)
    retorne documento.codigo + tamanho(documento.conteudo)
}
inicio {
    seja documentos: lista[Documento]
    seja documento: Documento
    documento.codigo = 10
    copie(documento.titulo, "Relatório")
    adicione_byte(documento.conteudo, 255)
    adicione(documentos, mova(documento))
    escreva(consultar(empreste(documentos[0])))
    escreva(tamanho(documentos))
}
```

A saída é `Relatório`, `11` e `1`. Também se pode passar
`empreste(documento)` quando o registro ainda pertence a uma variável local.
O índice é avaliado uma vez, antes da leitura; índices negativos, posições
fora do tamanho e listas inativas encerram com diagnóstico controlado.
Todas as folhas proprietárias são conferidas antes de transmitir a vista.

## Campos e duração

| Campo original | Campo recebido na vista |
|---|---|
| `inteiro`, `logico`, buffers e listas fixas | Valor de leitura, com cópia das palavras fixas |
| `texto` | `emprestimo[texto]` |
| `bytes` | `emprestimo[bytes]` |
| `lista[T]` dinâmica | `emprestimo[lista[T]]` |
| Subregistro | `emprestimo[Subregistro]` com as mesmas regras recursivas |

Campos podem ser consultados e retransmitidos a outras funções de leitura.
Um parâmetro de registro emprestado pode ser passado pelo próprio nome ou
com `empreste(parametro)`. Um subregistro pode ser retransmitido da mesma
forma. Para um elemento de coleção aninhada, use
`empreste(parametro.colecao[indice])`.

O empréstimo só existe durante a chamada e suas chamadas descendentes.
O compilador rejeita armazenamento local, retorno do empréstimo, movimento
dos campos, liberação, inserção/remoção e qualquer alteração dos campos,
incluindo escalares e buffers fixos. As escritas diretas são confrontadas
com os aliases de leitura pelo contrato compartilhado de efeitos; chamadas
recebem tipos de empréstimo para impedir alterações indiretas.

Copiar um escalar ou buffer fixo para um valor independente é permitido.
Para criar texto ou bytes independentes, `copie(destino, parametro.campo)`
faz uma cópia explícita. O novo dono pode sair da função, inclusive em um
resultado proprietário. O empréstimo inteiro nunca vira um novo dono.

## Aliases e alterações na coleção

Na mesma árvore de chamada, um elemento emprestado não pode compartilhar
sua lista com `mova` ou `retire`, independentemente da ordem dos argumentos.
A verificação inclui chamadas aninhadas e efeitos do índice. Também rejeita
o movimento de um registro pai que contém a lista, e o movimento de qualquer
folha de um registro local enquanto esse registro está emprestado.

Empréstimos simultâneos de leitura são permitidos. Após a chamada terminar,
o dono pode substituir, retirar, limpar, liberar ou ampliar sua coleção.
As funções RS não acessam variáveis globais; possíveis aliases chegam pelos
argumentos e são verificados na chamada. Não há referência persistente a
uma posição do heap.

## Disposição e custo

A largura e a ordem dos campos usam a disposição comum de tipos.
Descritores da RS continuam com três palavras: ponteiro, comprimento e
capacidade. Elementos do heap têm palavras crescentes; locais têm palavras
decrescentes. Para emprestar um elemento, o chamador adapta as palavras do
registro para uma reserva temporária na própria pilha, sem donos de descarte.
O parâmetro transmite as palavras fixas e um ponteiro por descritor dinâmico.

Texto, bytes e elementos de listas no heap não são copiados. Escalares,
descritores e buffers fixos são copiados para formar a vista; seu custo é
proporcional à largura do registro, incluindo a capacidade dos buffers fixos.
Uma vista de um registro local dispensa a adaptação do heap. Retransmissão
copia apenas as palavras da vista. Não é uma referência de custo constante
para registros de largura arbitrária.

Reservas temporárias, parâmetros e argumentos pendentes participam do
orçamento de 768 KiB. Permanecem a margem para o sistema, a sondagem de pilha
Windows, os metadados de desenrolamento e a convenção interna existente.
Não há novo alocador, coleta de lixo, nível de otimização ou dependência de
Python para executar os programas PE/ELF.

As expressões novas descrevem leitura da origem, escrita no temporário,
efeitos do índice e possibilidade de falha. Não transferem propriedade e
não são reordenadas através de chamadas de efeito desconhecido.

## Biblioteca e aplicação em RS

`padrao/documentos.rts` acrescenta quatro funções de leitura:

- `titulo_igual(documento, titulo)`: igualdade dos bytes UTF-8; não normaliza Unicode.
- `tamanho_conteudo(documento)`: comprimento binário em bytes.
- `localizar_titulo(documentos, titulo)`: primeira posição ou `-1`, sem retirar elementos.
- `somar_conteudos(documentos)`: soma dos comprimentos, com a aritmética verificada da RS.

Recebem empréstimos. As funções anteriores de criação e alteração continuam
consumindo seus parâmetros proprietários. Busca é linear, aceita coleção
vazia e não impõe limite arbitrário de quantidade.

`exemplos/aplicacoes/pesquisa_documentos_rs042i.rts` importa a biblioteca,
monta uma coleção, encontra um título, trata título ausente, calcula o total
e lê título/conteúdo de um elemento antes de limpar a coleção.

## Verificação

```text
python -m unittest testes.test_emprestimos_registros_rs042i -v
python -m unittest testes.test_abi_emprestimos_registros_rs042i -v
python -m unittest discover -s testes -v
python compilar.py exemplos/aplicacoes/pesquisa_documentos_rs042i.rts --alvo windows -O 8 -o pesquisa.exe
```

Para ELF, use `--alvo linux`. Os cenários centrais executam O0–O8 no sistema
nativo e geram ambos os formatos. Há regressões para 257 registros,
crescimento/reuso, consultas repetidas, UTF-8 vazio e grande, bytes, registros
e coleções aninhadas, retransmissão, ordem do índice, retornos, recursão,
argumentos de largura ímpar, temporários compostos, aliases e rejeições.
Buffers fixos grandes exercitam a sondagem e o limite da reserva da vista.

No Windows real, 100 consultas conservam 27 ponteiros e todo o conteúdo dos
nove registros, sem alocação/liberação durante a leitura. O alocador é negado
nessa fase para tornar uma tentativa inesperada observável. O descarte final
fecha as 30 alocações com 30 liberações, incluindo duas áreas antigas da lista.
São verificados oito registradores inteiros, dez vetoriais não voláteis, RSP,
estados de desenrolamento e exceções reais em funções com vistas.
Os três ensaios Windows são ignorados no Linux.

## Limites e próximo trabalho

O acesso ocorre dentro de uma função com parâmetro emprestado. A sintaxe
direta `colecao[indice].campo` e variáveis de referência persistentes ainda
não são suportadas. `empreste` não aceita um registro recém-produzido por
chamada/`retire`; primeiro receba o registro em uma variável proprietária.
Listas fixas não ganham empréstimo de elementos nesta revisão.

Empréstimos mutáveis, tipos recursivos, `lista[texto]`, resultados diretos de
listas e resultados aninhados permanecem pendentes. Os limites da RS 0.42H
para coleções proprietárias continuam válidos. A consulta não implementa
transações, SQL, motor gráfico, Studio ou autocompilação.

O próximo avanço útil é reunir esses recursos em um cadastro persistente em
RS: consultar sem retirar, atualizar por substituição explícita, gravar e
reabrir registros de texto/binário variável com validação do formato.
