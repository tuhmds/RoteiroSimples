# RS 0.42A.1 — Valores dinâmicos e funções proprietárias

Esta é a primeira entrega experimental da RS 0.42A, baseada na main
RS 0.41.5 (`840d308e75a7a5864367c9473741461fdfb2583b`).
Ela centraliza o contrato de valores e permite receber e devolver as
listas dinâmicas tipadas existentes. Não conclui toda a RS 0.42A.

O compilador de desenvolvimento continua em Python e gera diretamente
PE32+ Windows e ELF64 Linux. Os executáveis não dependem de Python,
coletor de lixo, montador externo ou outra máquina virtual.

## Contrato comum

`compilador/propriedade.py` distingue quatro classes:

| Classe | Regra |
|---|---|
| Valor | Pode ser copiado; inclui escalares, listas fixas, texto/bytes fixos e registros com campos copiáveis. |
| Proprietário | Possui exclusivamente uma região dinâmica; exige transferência explícita e descarte. Nesta entrega, são as listas dinâmicas. |
| Empréstimo | Referência temporária de leitura a um descritor; não possui nem descarta a região. |
| Recurso | Arquivos mantêm suas regras próprias de fechamento; não passam a aceitar o movimento de listas. |

O contrato consulta a disposição compartilhada de tipos. Cada lista
proprietária conserva o descritor histórico de três palavras de 64 bits:
ponteiro, comprimento e capacidade. Comprimento negativo representa um
descritor inativo após transferência ou liberação. Isso é um estado interno,
não um comprimento observável por um programa RS válido.

`backend/valores_dinamicos.py` concentra a inicialização e a invalidação do
descritor, a verificação de estado vivo e a transferência para parâmetros
e retornos. O armazenamento dos elementos permanece nas rotinas nativas de
listas, com crescimento geométrico e liberação pelo sistema.

## Transferência em expressões

`lista[]` continua sendo a forma histórica de `lista[inteiro]`.
`lista[T]` aceita os tipos de elementos já implementados: inteiros,
lógicos e registros copiáveis. Não significa uma lista fixa de `T` posições;
por exemplo, `lista[5]` continua sendo uma lista fixa de cinco inteiros.

```text
funcao criar() -> lista[inteiro] {
    seja dados: lista[inteiro]
    adicione(dados, 17)
    retorne mova(dados)
}

funcao acrescentar(dados: lista[inteiro], numero: inteiro) -> lista[inteiro] {
    adicione(dados, numero)
    retorne mova(dados)
}

inicio {
    seja origem = criar()
    seja atualizado: lista[inteiro] = acrescentar(mova(origem), 23)
    seja recebido = mova(atualizado)
    escreva(recebido[1])
}
```

Depois de `mova(origem)`, a origem fica inativa. A função passa a possuir a
lista recebida. Se retornar `mova(dados)`, transfere novamente a propriedade
antes da limpeza da função. Se não transferir seu parâmetro, a limpeza o
descarta. A limpeza ignora descritores inativos para não liberar novamente
o armazenamento que já foi entregue.

A chamada transporta somente as três palavras do descritor. Ela não aloca
outra coleção nem copia os elementos. A criação da lista e operações que
precisem aumentar sua capacidade podem alocar normalmente.

Uma função proprietária pode receber diretamente o resultado novo de
outra função, sem `mova` sobre a chamada:

```text
funcao encaminhar() -> lista[inteiro] {
    retorne criar()
}

inicio {
    seja resultado = acrescentar(encaminhar(), 23)
    escreva(tamanho(resultado))
}
```

As formas válidas são:

| Posição | Formas aceitas |
|---|---|
| Parâmetro proprietário | `mova(variavel)` ou chamada que devolve o tipo proprietário exigido |
| Retorno proprietário | `retorne mova(variavel)` ou `retorne chamada_proprietaria()` |
| Declaração nova | `seja destino = mova(origem)` ou `seja destino = chamada_proprietaria()`; a anotação `: lista[T]` é opcional quando o tipo pode ser inferido |
| Destino já declarado | `mova(destino, origem)`, a operação histórica |

`mova(origem)` exige uma variável proprietária simples e ativa.
`mova(criar())`, cópia implícita com `seja copia = origem`,
argumento proprietário sem movimento e `retorne origem` são rejeitados.
A atribuição `destino = mova(origem)` também é rejeitada; para substituir
um dono existente, use `mova(destino, origem)`. A forma de dois argumentos
descarta o antigo conteúdo de destino antes de transferir o da origem.

Declarações, parâmetros, retornos e temporários compostos mantêm a
tipagem do elemento. Uma lista de lógicos não pode ser passada a uma
função que exige uma lista de inteiros.

## Empréstimos e erros de propriedade

A consulta sem consumo permanece explícita:

```text
funcao quantidade(dados: emprestimo[lista[inteiro]]) -> inteiro {
    retorne tamanho(dados)
}

inicio {
    seja dados = criar()
    escreva(quantidade(empreste(dados)))
    escreva(dados[0])
}
```

Empréstimos são de leitura e duram apenas a chamada síncrona. Eles podem
ser repassados a outras funções de leitura, mas não ser armazenados em
variáveis, retornados como referência persistente, transformados em donos
ou usados para modificar a coleção.

O compilador percorre a expressão completa dos argumentos para rejeitar
consumo duplicado e empréstimo/consumo do mesmo dono, inclusive quando as
operações estão em chamadas aninhadas e nas duas ordens de avaliação.
Duas consultas do mesmo dono são válidas; consultar um dono e consumir
outro também é válido.

Esta entrega não faz uma prova estática completa do estado dos donos em
todos os caminhos do programa. Depois de um movimento ou liberação,
operações que exigem o dono ativo continuam verificadas no executável.
Uso inválido encerra com diagnóstico; não produz uma referência
persistentemente reutilizável.

## Biblioteca e aplicação escritas em RS

`importe "padrao/listas.rts" como listas` oferece cinco novas funções
para listas dinâmicas de inteiros, sem restringir a consulta a cinco posições:

| Função | Resultado |
|---|---|
| `buscar(empreste(valores), procurado)` | Índice da primeira ocorrência, ou `-1` |
| `contar(empreste(valores), procurado)` | Quantidade de ocorrências |
| `contem(empreste(valores), procurado)` | Valor lógico indicando presença |
| `crescente(empreste(valores))` | Valor lógico indicando ordem não decrescente; lista vazia também satisfaz a consulta |
| `selecionar_intervalo(empreste(valores), minimo, maximo)` | Nova lista proprietária com valores no intervalo inclusivo, preservando a ordem |

As quatro consultas não copiam a coleção. A seleção cria seus próprios
elementos e devolve a nova coleção; a original permanece disponível.
As funções históricas com sufixo `_cinco` continuam disponíveis.

`exemplos/aplicacoes/cadastro_pessoas_rs042a.rts` demonstra a composição
das operações em uma aplicação RS. Ela cria três pessoas com código, idade
e crédito inteiro em centavos; pesquisa por empréstimo; recebe e devolve
o cadastro para atualizar uma idade; soma os créditos; cria `cadastro.rsd`
com exclusividade e lê novamente os registros.

O formato demonstrativo usa 24 bytes por pessoa: três inteiros de 64 bits,
com byte menos significativo primeiro. Os valores do exemplo são
não negativos. A leitura rejeita registros incompletos e campos inválidos.
O exemplo não é um banco de dados versionado nem oferece atualização
transacional. Ele recusa sobrescrever um destino já existente.
Nomes de pessoas com comprimento variável aguardam texto dinâmico.

```text
python compilar.py exemplos/aplicacoes/cadastro_pessoas_rs042a.rts --alvo windows -O 8 -o cadastro.exe
python compilar.py exemplos/aplicacoes/cadastro_pessoas_rs042a.rts --alvo linux -O 8 -o cadastro
```

Execute no sistema correspondente em uma pasta sem `cadastro.rsd`.
A entrada de demonstração é código `2`, seguido de idade `37`.

## Segurança revisada neste marco

A gravação indexada precisa verificar que o destino ainda está ativo
depois de avaliar o valor. A expressão à direita pode consumir o próprio
dono, como em `dados[0] = consumir(mova(dados))`. A nova verificação
interrompe esse caso com diagnóstico antes da escrita por ponteiro
inválido. Consumir outra lista continua permitido.

A descoberta de chamadas recursivas percorre a árvore inteira, incluindo
índices, expressões de acréscimo e retornos proprietários. A inicialização
de descritores também não pode apagar o orçamento de pilha recebido.

**Proteção de pilha:** a revisão do orçamento contabiliza
o quadro principal, os quadros de todas as funções, os argumentos,
os argumentos ocultos, o alinhamento e os temporários já empilhados.
A verificação ocorre antes de preparar a próxima chamada,
inclusive durante a avaliação de chamadas aninhadas. Quadros principais
que já excedam o orçamento são rejeitados na compilação. A sondagem
Windows recupera o orçamento após a chamada auxiliar, que pode alterar
registradores voláteis.

A política revisada usa 768 KiB para o orçamento RS em ambos os alvos.
No PE, que reserva 1 MiB de pilha, ficam 256 KiB fora desse orçamento
para a entrada do sistema, rotinas auxiliares e diagnóstico.
Essa reserva é uma margem operacional, não uma prova universal de
segurança da pilha. Sondagem de páginas, ABI e metadados Windows da
0.41.5 continuam parte das regressões obrigatórias.

## Compatibilidade e migração

Comparações diretas entre listas proprietárias agora são rejeitadas.
O caminho antigo comparava ponteiros e não expressava igualdade de
conteúdo. Para comparar conteúdo, consulte tamanhos e elementos por
empréstimo e aplique a regra da aplicação. Não há operador novo de
igualdade estrutural de listas nesta entrega.

A política antiga anunciava até 1 MiB no trecho recursivo.
O orçamento revisado de 768 KiB inclui chamadas e temporários que
antes ficavam fora da conta. Programas com cadeias de chamadas ou
quadros grandes próximos ao limite podem encerrar mais cedo.
Reduza os quadros locais ou use as listas dinâmicas já disponíveis
para os dados que precisam crescer. Isso não introduz um limite fixo
de quantidade de elementos no armazenamento dinâmico.

As formas históricas de listas fixas, texto/bytes de capacidade fixa,
movimento de dois argumentos e empréstimo imutável são mantidas.
Nenhum nível de otimização adicional é criado.

## Efeitos e otimização

`mova_valor_dinamico` e `receba_valor_dinamico` possuem efeitos explícitos
de propriedade. Consultas de tamanho/capacidade e criação de empréstimos
dinâmicos registram a possibilidade de falha por dono inativo.
Chamadas continuam sendo barreiras conservadoras entre funções.

Programas com esses recursos usam o gerador conservador de O0 a O8.
A IR/SSA ainda não modela integralmente as funções e transições de
propriedade; selecionar `-O 8` não muda essa restrição. O diagnóstico
`--mostrar-estrategia` informa a escolha real, e
`--mostrar-efeitos-do-programa` inspeciona a árvore completa.

## Validação reproduzível

A [integração contínua da PR](https://github.com/tuhmds/RoteiroSimples/actions/runs/38372044241)
aprovou o commit `acb65af`, incluindo a regressão adicional de índices e
temporários. As alterações posteriores deste registro são documentais.

| Sistema | Testes encontrados | Aprovados | Ignorados | Falhas |
|---|---:|---:|---:|---:|
| Windows x64 | 487 | 475 | 12 | 0 |
| Linux x86-64 | 487 | 467 | 20 | 0 |

Cada sistema executou seus próprios binários nativos. No Linux, os ensaios
da API Windows e da ABI Windows são ignorados; no Windows, os ensaios
específicos de Linux são ignorados. A suíte local anterior executou 486
testes Windows com 13 ignorados, mais a regressão adicional aprovada
isoladamente; a diferença de um ignorado decorre da permissão de criar
link simbólico na máquina local. Os 46 testes novos ampliam a base de 441.

As verificações Windows confirmaram diagnóstico controlado em recursão
com quatro ou dez donos e com doze argumentos pendentes durante outra
chamada. Quadros principais e de função com buffer de 600000 bytes
funcionam isoladamente; duas reservas grandes encadeadas ou uma cópia
de argumentos desse porte recebem diagnóstico antes de empilhar.
Um quadro principal de 800000 bytes é rejeitado na compilação para
ambos os alvos. A recursão com quadro sondado de 7000 bytes funciona
com profundidade pequena e recebe diagnóstico na profundidade excessiva.
As regressões de metadados e das 22 rotinas auxiliares Windows permanecem
na suíte aprovada.

Os testes acrescentados cobrem o contrato e a tipagem, listas vazias e
maiores, lógicos e registros, transferência encadeada, temporários,
retornos antecipados, escopos, valores gerados com semente fixa, uso
após consumo, índices inválidos, alocação simuladamente recusada,
recursão com muitos argumentos e chamadas aninhadas, biblioteca e
cadastro persistente. A execução nativa portável percorre O0–O8 nos
cenários funcionais; os casos de esgotamento de pilha usam O0 e O8.

O ensaio específico Windows observa o ponteiro, conteúdo, comprimento,
capacidade e chamadas reais de alocação/liberação. Ele verifica que
transportar a lista não cria outra alocação, que o descarte final
ocorre uma vez e que oito registradores inteiros, dez vetoriais e
`RSP` são preservados. Esse hospedeiro de testes não cria uma interface
pública de interoperabilidade na linguagem.

A partir da raiz do repositório:

```text
python -m unittest testes.test_propriedade_rs042a testes.test_funcoes_proprietarias_parser_rs042a testes.test_valores_dinamicos_rs042a testes.test_abi_proprietarios_rs042a -v
python -m unittest discover -s testes -v
```

No Linux, use `python3` se esse for o nome do Python instalado. Cada
sistema executa seus próprios binários nativos. Os ensaios Windows de
desenrolamento real da 0.41.5 continuam na suíte completa.

## Próximos marcos

Texto UTF-8 dinâmico e bytes dinâmicos precisam compartilhar alocação,
reserva, transferência e descarte, respeitando as unidades de bytes
e a validação de texto. Depois vêm donos em registros e coleções,
empréstimos mutáveis, funções genéricas gerais, novos operadores
lógicos e tipos reais/decimais. O tipo `logico` existente e as listas
de lógicos já fazem parte desta entrega; não devem ser confundidos
com esses operadores futuros.

A linguagem segue experimental, sem autocompilação, garantias formais
de memória segura, mecanismo geral de exceções recuperáveis,
transações de arquivo ou causa comprovada para a falha de
`HIGH_ENTROPY_VA`. Essa opção permanece desativada.
