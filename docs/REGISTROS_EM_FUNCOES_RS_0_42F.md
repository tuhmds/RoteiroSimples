# RS 0.42F — Registros proprietários em funções

Esta nota descreve o marco 0.42F. A [0.42G acrescentou resultados com donos](RESULTADOS_PROPRIETARIOS_RS_0_42G.md); os limites abaixo relativos a resultados descrevem a entrega original.

## Contrato da entrega

Registros com folhas `texto`, `bytes`, `lista[inteiro]` e `lista[logico]`
podem ser parâmetros e retornos de funções. Podem conter subregistros com
essas folhas e campos copiáveis já suportados, incluindo buffers fixos.
Um argumento ou retorno proprietário exige `mova(origem)` ou uma chamada
que produza um valor novo do mesmo tipo. O tipo nominal deve coincidir.

```text
tipo Documento {
    titulo: texto
    conteudo: bytes
}
funcao criar() -> Documento {
    seja documento: Documento
    copie(documento.titulo, "Relatório")
    adicione_byte(documento.conteudo, 65)
    retorne mova(documento)
}
funcao transportar(documento: Documento) -> Documento {
    retorne mova(documento)
}
inicio {
    seja origem: Documento = criar()
    seja destino = transportar(mova(origem))
    seja outro = transportar(criar())
    escreva(destino.titulo)
    escreva(outro.conteudo[0])
}
```

`seja destino: Documento = mova(origem)` e a declaração com tipo inferido
também transferem o agregado. Para um destino já declarado, permanece
`mova(destino, origem)`, que descarta o conteúdo antigo após validar a origem.
Um subregistro pode ser transferido por seu caminho completo, como
`mova(documento.dados)`, sem consumir os demais campos proprietários.

## Representação e descarte

Um registro proprietário conserva sua largura completa calculada pela
disposição comum; não vira um descritor de três palavras. Cada folha dinâmica
mantém seu descritor próprio. O contrato comum identifica o agregado como
`agregado_proprietario`, não copiável e sujeito a descarte.

O transporte copia as palavras do agregado e conserva os ponteiros para o
conteúdo dinâmico. Todos os donos da origem são validados antes do transporte
e inativados depois. Nenhum novo armazenamento é alocado só para transferir.
Os campos copiáveis mantêm a semântica histórica por valor.

O chamador oferece o destino oculto para retornos compostos. Parâmetros são
recebidos em slots privados do chamado, que passa a possuir seus campos.
Resultados intermediários de chamadas têm campos mapeados no mesmo quadro,
inicializados inativos na entrada. Após passados ao próximo chamado, seus
donos são inativados. A limpeza comum percorre as folhas uma vez; o agregado
não recebe um segundo descarte independente.

Cada caminho de campo recebe um alias próprio, mesmo quando um subregistro
e seu primeiro campo têm o mesmo nome e endereço. Isso preserva o tipo do
subregistro e permite transferi-lo separadamente sem colisão de metadados.

Saídas de bloco, `pare`, `continue` e término da função liberam os campos
que ainda têm dono. Ao devolver o agregado, seus campos deixam de participar
do descarte da origem. Registros sem folhas proprietárias continuam aceitando
cópias implícitas, parâmetros e retornos por valor.

## Verificações

O analisador rejeita cópia implícita de agregados proprietários em argumentos,
retornos, inicializações, atribuições e comparação direta. Em uma árvore de
chamada, resolve o conjunto de folhas para detectar consumo sobreposto entre
registro, subregistro e campo, inclusive em argumentos aninhados. Também
rejeita emprestar um campo e consumir seu agregado na mesma chamada,
independentemente da ordem dos argumentos. Campos disjuntos podem ser consumidos.

As consultas e operações de campos movidos continuam encerrando com o erro
controlado de valor inativo. A movimentação ou retorno de um registro com
qualquer folha já consumida falha antes de transportar o agregado. Para
completá-lo, devolva explicitamente um dono ao campo com `mova(destino, origem)`.
A vida de campos escalares não é invalidada por essa marca de descritor.

O orçamento de pilha existente inclui a largura dos argumentos, destinos
ocultos, temporários e quadros. A recursão continua com limite seguro de
768 KiB. O gerador conservador atende esses programas de `-O 0` a `-O 8`.
Os executáveis permanecem PE/ELF nativos sem dependência de Python.

## Provas reproduzíveis

```text
python -m unittest testes.test_registros_funcoes_rs042f -v
python -m unittest testes.test_abi_registros_funcoes_rs042f -v
python -m unittest discover -s testes -v
python compilar.py exemplos/aplicacoes/documento_registro_rs042f.rts --alvo windows -O 8 -o documento.exe
```

Para Linux, use `--alvo linux` e execute o ELF x86-64 gerado.
Os testes portáveis geram ambos os formatos e executam no sistema real.
Cobrem fábricas, movimentos em declarações, retornos encaminhados, argumentos
mistos, campos fixos, registros copiáveis, temporários em laços, retornos
antecipados, campos homônimos, estado parcial, falha simulada de alocação e
limite de recursão. Os cenários centrais de
chamadas, alinhamento e compatibilidade percorrem os nove níveis; os demais
usam `-O 0` e `-O 8`.

No Windows real, o hospedeiro verifica os ponteiros de dois heaps distintos,
ausência de alocação durante transporte, os ponteiros liberados e o descarte
de temporários em três iterações. Verifica oito registradores inteiros, dez
vetoriais não voláteis e RSP em cada chamada. Ensaios separados usam
`RtlVirtualUnwind` em estados de prólogo/epílogo e exceções reais nas funções.
Esses testes são ignorados no Linux; os testes de execução ELF permanecem ativos.

## Limites e continuidade

Ainda são rejeitados `lista[RegistroProprietario]`, campos contendo listas de
registros, `emprestimo[Registro]`, recursos `arquivo` em campos/assinaturas e
`resultado[T]` com valores proprietários. Resultados genéricos existentes
continuam por valor, sem relaxar a rejeição de cópia de donos nos construtores.
Não há empréstimos mutáveis, FFI geral, tipos reais/decimais ou novas regras
de tratamento de falhas de alocação recuperáveis nesta revisão.

Para o Dados RS, este marco permite separar criação, transformação e consumo
de registros com conteúdo variável. Para o compilador e o Studio, permite
transportar estruturas com texto e bytes entre funções em RS. A revisão não
implementa um motor transacional, uma interface gráfica ou a autocompilação.
