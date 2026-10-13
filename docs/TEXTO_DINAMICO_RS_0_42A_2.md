# RS 0.42A.2 — Texto UTF-8 dinâmico

Esta entrega parte do commit `7603053`, marco de propriedade RS 0.42A.1.
A branch `rs-0.42a-texto-dinamico` mantém essa dependência. A ordem de
integração é propriedade, texto e bytes; a
[revisão conjunta](REVISAO_CONJUNTA_RS_0_42A.md) registra a verificação posterior.

O critério funcional de texto dinâmico está implementado: um programa RS
pode ler, construir, acrescentar, limpar, transferir, devolver e gravar
texto de comprimento variável sem declarar capacidade fixa. A execução
continua diretamente nativa PE32+/ELF64, sem Python no executável.

## Sintaxe e unidades

```text
funcao completar(nome: texto) -> texto {
    junte(nome, "😀")
    retorne mova(nome)
}

inicio {
    seja nome: texto
    leia(nome)
    seja concluido = completar(mova(nome))
    escreva(concluido)
    escreva(tamanho(concluido))
    escreva(caracteres(concluido))
    grave_arquivo("nome.txt", concluido)
}
```

| Operação | Regra |
|---|---|
| `seja nome: texto` | Proprietário vazio, comprimento/capacidade zero, sem alocação inicial |
| `seja nome: texto = "ação"` | Construção UTF-8; literal validado pelo compilador |
| `copie(destino, origem)` | Cópia explícita de conteúdo; aceita literal, texto fixo, dinâmico ou emprestado |
| `junte(destino, origem)` | Acrescenta conteúdo; aceita a própria origem, incluindo realocação |
| `limpe(destino)` | Comprimento zero, mantendo a reserva para reutilização |
| `libere(destino)` | Descarte explícito e descritor inativo |
| `mova(origem)` | Passa dono a declaração, parâmetro ou retorno |
| `mova(destino, origem)` | Descarta o antigo destino e transfere o descritor |
| `empreste(origem)` | Referência de leitura síncrona para `emprestimo[texto]` |
| `tamanho(nome)` / `capacidade(nome)` | Bytes de conteúdo / reserva de bytes |
| `caracteres(nome)` | Valores escalares Unicode, com UTF-8 validado |
| `byte_em(nome, indice)` | Byte de 0 a 255; índice em bytes e limites verificados |
| `nome == outro` / `nome != outro` | Igualdade exata do conteúdo de variáveis, incluindo texto fixo/emprestado |

`caracteres` não conta grafemas visuais. Por exemplo, `e` seguido de
U+0301 possui três bytes UTF-8 e dois valores escalares. Não há normalização
implícita: essa sequência e U+00E9 têm conteúdos diferentes. Não há
indexação Unicode por `nome[indice]` nem ordenação cultural implícita.
`byte_em` é deliberadamente uma consulta de unidade binária, sem mutação.

O validador verifica as restrições da [RFC 3629](https://www.rfc-editor.org/rfc/rfc3629):
continuações, sequências completas, ausência de codificações mais longas
que o necessário, exclusão de substitutos UTF-16 e teto U+10FFFF.
U+0000 é permitido e preservado; comprimento explícito não depende de NUL.

## Propriedade e memória compartilhada

Texto usa o descritor de três palavras já estabelecido: ponteiro,
comprimento e capacidade, com comprimento negativo para estado inativo.
O contrato central usa passo de um byte para texto e oito bytes por
palavra do elemento de lista. Não foi criado outro gerenciador de memória.

`backend/memoria_dinamica.py` concentra alocação nativa, reserva geométrica,
cópia dos bytes vivos na expansão, liberação e movimento. As listas também
passam por essas rotinas. Adaptadores preservam as convenções históricas
das rotinas `rs_lista_*` cujas larguras eram passadas em palavras.
Transferência transporta somente o descritor, sem alocar ou copiar conteúdo.

Soma de comprimento, crescimento e multiplicação capacidade/passo têm
verificação de estouro. A reserva nova antecede a liberação antiga e a
atualização do descritor. Falha de memória encerra com diagnóstico.
O limite histórico da largura de registros é mantido no contrato central,
com erro de compilação legível, em vez de falha ao empacotar um imediato.

Empréstimos não são armazenáveis, retornáveis ou mutáveis. Cópias implícitas,
reatribuição de donos e consumo duplicado continuam rejeitados. O consumo
e empréstimo do mesmo dono na árvore de chamada também são rejeitados.
Estados após movimento/liberação são conferidos no executável. Limpeza por
escopo, retorno, `pare` e `continue` aplica o descarte comum aos textos.

## Entrada, saída e arquivos

`leia(texto)` usa o mesmo cache da entrada inteira/fixa, preservando bytes
após a quebra de linha. LF termina a linha; CR final é removido conforme
a regra histórica de CRLF. EOF pode concluir uma linha sem quebra.
O conteúdo é validado antes do retorno. Leitura do teclado dentro de
funções continua indisponível; o principal pode passar o texto às funções.

`carregue_arquivo` cresce até EOF e valida o conteúdo completo. Uma prova
de um byte antecede o crescimento quando a reserva está cheia: arquivo
vazio não aloca, e EOF na fronteira não provoca uma realocação desnecessária.
`grave_arquivo` e impressão transferem em blocos de até 1 MiB e repetem
operações parciais; esse bloco não limita o tamanho total do conteúdo.

Os comandos reaproveitam abertura, inspeção e fechamento existentes,
com caminhos literais verificados e proteção contra links/reparse points.
`grave_arquivo` mantém a semântica histórica de substituir conteúdo de um
destino regular. Não é publicação transacional: erro pode deixar gravação
parcial. O projeto já oferece publicação de arquivo como operação separada.
Arquivos posicionais e caminhos variáveis ainda não aceitam o novo texto.

`texto[N]` e `bytes[N]` continuam disponíveis. Cópia de texto dinâmico para
texto fixo respeita sua capacidade e falha antes de truncar; cópia de um
buffer fixo para dinâmico valida UTF-8. Dados binários arbitrários não são
implicitamente convertidos em texto.

## Biblioteca e aplicação RS

`importe "padrao/textos.rts" como textos` oferece `duplicar`, `concatenar`
e `vazio`, implementados em RS. As duas primeiras criam outro dono com
cópia de conteúdo explícita; a consulta não consome a origem.

`exemplos/aplicacoes/documento_utf8_rs042a.rts` recebe um nome sem capacidade
declarada, valida a presença, constrói e transfere o documento entre funções,
grava `pessoa_utf8.txt`, recupera e compara o conteúdo. A entrada vazia é
rejeitada. O cadastro numérico anterior foi preservado; nomes dentro dos
registros aguardam o suporte seguro a elementos com propriedade interna.

```text
python compilar.py exemplos/aplicacoes/documento_utf8_rs042a.rts --alvo windows -O 8 -o documento.exe
python compilar.py exemplos/aplicacoes/documento_utf8_rs042a.rts --alvo linux -O 8 -o documento
```

## Efeitos, ABI e validação

Os nós novos possuem leitura/escrita de memória, eventos de propriedade
e possibilidade de falha no contrato de efeitos. Comparação textual tem
nó próprio, distinto da comparação escalar e da comparação de ponteiros.
Programas com texto novo continuam no gerador conservador de O0 a O8;
nenhum O9 foi criado e a IR não foi anunciada como plenamente compatível.

Offsets dos parâmetros e retornos internos são preservados. Windows recebe
metadados verificados para os nove auxiliares novos de memória, texto e
carregamento. O ensaio real cobre prólogos, corpos, epílogos e exceções INT3.
O teste de transporte observa o mesmo ponteiro/conteúdo/capacidade,
zero alocações ou liberações durante o movimento, um descarte final,
descarte correto em laços/saídas e oito registradores inteiros/dez vetoriais/RSP.
Essa instrumentação de teste não oferece interoperabilidade na linguagem.

Windows local: 527 testes encontrados, sem falhas, 13 ignorados por plataforma
ou permissão de link simbólico. Os 40 testes novos incluem listas históricas por gerenciador
comum, texto vazio/grande, UTF-8 com NUL, limites legais, codificações inválidas,
expansão/reutilização, arquivo maior que 1 MiB, transferência e escopos,
falha de alocação simulada, overflow de tamanho e recursão controlada.
A [CI aprovada](https://github.com/tuhmds/RoteiroSimples/actions/runs/38382667977)
executou o commit `1fabb24` nos dois sistemas, incluindo a correção e a
regressão de registros emprestados. Cada sistema executa seu próprio binário.

| Sistema | Encontrados | Aprovados | Ignorados | Falhas |
|---|---:|---:|---:|---:|
| Windows x64 | 527 | 515 | 12 | 0 |
| Linux x86-64 | 527 | 504 | 23 | 0 |

Os ignorados são específicos da plataforma; os três ensaios novos da API
Windows não são executados no Linux. O ignorado adicional local decorre
da permissão de criar link simbólico. A PR depende da PR de propriedade;
nenhuma das entregas foi mesclada automaticamente.

A primeira CI detectou uma regressão na leitura de registros emprestados
após a centralização da largura: o cálculo do passo aceitava apenas o tipo
proprietário. O passo agora reconhece a mesma representação do conteúdo para
donos e empréstimos, preservando suas regras distintas de disposição e
descarte. A regressão específica compila os dois alvos e executa O0–O8;
a suíte completa local foi repetida e aprovada depois da correção.

```text
python -m unittest testes.test_texto_dinamico_parser_rs042a testes.test_texto_dinamico_nativo_rs042a testes.test_abi_texto_dinamico_rs042a -v
python -m unittest discover -s testes -v
```

Permanecem pendentes bytes dinâmicos, proprietários dentro de registros/listas,
empréstimos mutáveis, segmentação de grafemas, busca/fatiamento Unicode,
genéricos gerais, novos operadores lógicos, reais/decimais e autocompilação.
Falhas fatais não são exceções recuperáveis da linguagem.
`HIGH_ENTROPY_VA` permanece desativado.
