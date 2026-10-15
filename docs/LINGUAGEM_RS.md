# A linguagem RoteiroSimples — referência consolidada

**Versão: RS 0.42U, experimental.** Esta página reúne o contrato de uso atual.
As notas por versão registram implementação e ensaios; propostas futuras não
se tornam sintaxe aceita por aparecerem em um documento. A gramática da 0.9
é histórica. Esta referência não anuncia estabilização da futura RS 1.0.

## Programa, nomes e organização

Um arquivo `.rts` contém, nesta ordem, importações, definições de registros,
funções e o bloco `inicio`. Um módulo de biblioteca pode fornecer definições
sem um bloco principal. `importe "padrao/textos.rts" como textos` importa
um módulo oficial; caminhos locais e visibilidade são descritos no
[contrato de módulos](../README.md#organização-atual).

Comandos e identificadores usam ASCII, sem acentos, e distinguem maiúsculas
de minúsculas. Textos literais usam aspas duplas, UTF-8 e escapes JSON, como
`"Ação 🌱"`, `"\n"` e `"\u0000"`. `//` inicia comentário fora do literal.
Cada instrução ocupa uma linha; o ponto e vírgula final é opcional.
Cabeçalhos e chaves finais ocupam linhas próprias, admitindo `} senao {`.

```text
funcao dobro(numero: inteiro) -> inteiro {
    retorne numero * 2
}
inicio {
    seja numero = 5
    se numero > 0 {
        escreva(dobro(numero))
    } senao {
        escreva(0)
    }
}
```

Funções têm parâmetros e retorno explícitos; argumentos são avaliados da
esquerda para a direita. Retornos devem cobrir os caminhos necessários.
`publico` e `privado` controlam definições nos módulos. Variáveis têm escopo
léxico; nomes locais podem ocultar nomes de escopos externos. Os nomes
internos começados por `__rs_` são reservados.

## Tipos disponíveis

| Escrita | Significado e propriedade |
| --- | --- |
| `inteiro` | Inteiro assinado de 64 bits, com limites verificados nas operações |
| `logico` | `verdadeiro` ou `falso` |
| `texto[N]` | Buffer copiável, capacidade fixa em bytes UTF-8 |
| `bytes[N]` | Buffer copiável de bytes arbitrários |
| `lista[N]` | Lista fixa de N inteiros; N é capacidade literal, não tipo |
| `texto` | Texto UTF-8 crescente, dono exclusivo |
| `bytes` | Sequência binária crescente, dona exclusiva |
| `lista[]` / `lista[inteiro]` | Lista crescente de inteiros, dona exclusiva |
| `lista[logico]` | Lista crescente de lógicos |
| `lista[MeuRegistro]` | Lista de registros do tipo declarado, incluindo donos |
| `lista[texto]` | Lista crescente que possui cada texto |
| `MeuRegistro` | Campos por valor; proprietário quando contém donos |
| `emprestimo[T]` | Leitura temporária, somente para tipos e parâmetros suportados |
| `resultado[T]` | Sucesso/falha especializado para os tipos concretos suportados |
| `arquivo` | Recurso local com fechamento controlado; não é um inteiro copiável |

Tipos reais e decimais, ponteiros brutos, FFI, empréstimos mutáveis, listas
diretas de bytes/donos arbitrários e tipos recursivos ainda não fazem parte
desse contrato. `lista[texto]` não habilita `lista[lista[texto]]`.
Empréstimos e recursos de arquivo não podem ser retornados ou armazenados
como valores comuns. Não há funções genéricas gerais.

Um inteiro usa uma palavra de oito bytes; isso não é a largura universal de
uma variável. Descritores de texto/bytes/listas usam três palavras, registros
somam os campos e buffers fixos reservam seu conteúdo. Cada função possui
quadro próprio. A constante histórica `MAX_VARIAVEIS=256` não limita o total
de variáveis de um programa. O caminho SSA sem funções ainda limita suas
vagas de pilha; chamadas RS usam orçamento acumulado de 768 KiB e sondagem.
Há outros limites de endereçamento e de aninhamento documentados por recurso.

## Expressões e controle

Precedência, da maior para a menor: parênteses/chamadas/acessos, sinal
unário, `* / %`, `+ -`, comparações, `nao`, `e`, `ou`.
`e`, `ou` e `nao` exigem lógicos; os dois primeiros preservam curto-circuito.
Comparações disponíveis: `== != < <= > >=`; ordenação exige inteiros.
Textos dinâmicos admitem igualdade de conteúdo, sem normalização Unicode.
Registros e donos não ganham comparação estrutural implícita.

`se` e `enquanto` aceitam condição lógica ou inteira: zero é falso.
`para contador de primeiro ate ultimo` inclui os extremos, com passo padrão
1; `passo` aceita inteiro literal de -9223372036854775807 a 9223372036854775807,
exceto zero. `pare` sai do laço e
`continue` avança para a próxima iteração, conservando o descarte de escopo.
Não há expressão de atribuição nem conversão implícita geral entre tipos.

```text
declaracao = "seja" nome [ ":" tipo ] [ "=" expressao ]
funcao = [ visibilidade ] "funcao" nome "(" parametros ")" "->" tipo bloco
condicao = "se" expressao bloco [ "senao" bloco ]
laco = "enquanto" expressao bloco
     | "para" nome "de" expressao "ate" expressao [ "passo" inteiro_literal ] bloco
retorno = "retorne" expressao
bloco = "{" quebra_de_linha instrucoes "}"
```

Essa notação resume o núcleo estrutural; as restrições de inicialização e
operações são determinadas pelo tipo. Uma lista dinâmica nasce vazia;
`seja nome: texto = "RS"` cria um dono novo. Cópias de texto usam `copie`;
`junte` acrescenta conteúdo ao destino. Os comandos de entrada, arquivos e
recursos são operações próprias, não chamadas arbitrárias intercambiáveis.

## Propriedade, coleções e resultados

- `mova(origem)` transfere um dono para parâmetro, retorno ou declaração;
  `mova(destino, origem)` substitui o dono do destino. A origem fica inativa.
- `empreste(origem)` oferece leitura durante a chamada, sem transferir o dono.
  `empreste(nomes[indice])` consulta um texto de `lista[texto]` ou um registro
  de coleção. Não se pode guardar esse empréstimo em variável local.
- `adicione(lista, mova(valor))` ou uma chamada que produza valor novo
  transfere o elemento para a coleção. Cópias implícitas de donos são recusadas.
- `retire(lista, indice)` remove e transfere o elemento. Substituição por
  índice descarta o elemento anterior; `remova_ultimo` descarta o último;
  `limpe_lista` descarta todos e conserva a capacidade; `libere` libera a lista.
- Donos são descartados ao sair de seus escopos, inclusive por retorno,
  `pare` ou `continue`. Índices e usos de donos inativos são verificados.

A análise recusa consumos duplicados e conflitos de movimento/empréstimo
na mesma árvore de chamada. Algumas verificações de vida permanecem em
execução. Isso não constitui uma prova de segurança integral de memória.

`sucesso[T](valor)` e `falha[T](codigo)` constroem `resultado[T]`.
`propague resposta` devolve a falha quando necessário e continua em sucesso;
não extrai automaticamente o valor. Tipos concretos aceitos incluem escalares,
texto, bytes, registros suportados, buffers fixos previstos e listas dinâmicas
dos tipos aceitos pelo parser, como `resultado[lista[texto]]`.
Resultados aninhados e resultados de empréstimos/arquivo seguem indisponíveis.

Para extrair um dono, verifique `resposta.valido` e use `mova(resposta.valor)`.
Os campos `valido`, `codigo_erro` e `valor` permanecem públicos por compatibilidade;
mover o valor não altera automaticamente `valido`. O estado não substitui a
verificação de vida do conteúdo.

## Biblioteca de textos

| Função em `padrao/textos.rts` | Contrato |
| --- | --- |
| `duplicar`, `concatenar`, `vazio` | Operações anteriores preservadas |
| `encontrar(origem, procurado)` | `resultado[inteiro]`; posição em caracteres, -1 ausente, 0 para padrão vazio |
| `recortar(origem, posicao_inicial, quantidade)` | `resultado[texto]`; posições em caracteres, sem dividir UTF-8 |
| `separar(origem, separador)` | `resultado[lista[texto]]`; preserva partes vazias; recusa separador vazio |
| `juntar(partes, separador)` | `resultado[texto]`; lista vazia produz texto vazio |
| `aparar(origem)` | `resultado[texto]`; remove ASCII 9..13 e 32 nas extremidades, preservando espaços internos e Unicode |

Os parâmetros de leitura recebem empréstimos. As posições contam valores
escalares Unicode, não bytes nem grafemas: um acento combinante conta como
outro caractere, e não há normalização implícita. `tamanho(texto)` conta bytes;
`caracteres(texto)` conta esses valores Unicode; `byte_em` consulta um byte.

Erros recuperáveis das operações novas: 1 UTF-8 inválido na conversão usada
pela operação; 2 posição inicial inválida; 3 quantidade inválida; 4 separador
vazio. Para entrada externa, carregue bytes e use `padrao/utf8.rts` para
decodificar com resultado explícito. A carga direta de texto conserva as
falhas fatais do comando existente.

O exemplo [ler_configuracao_rs042t.rts](../exemplos/ferramentas/ler_configuracao_rs042t.rts)
lê um arquivo UTF-8 de linhas `chave=valor`, admite comentários de linha `#`
e informa a linha de uma entrada inválida. É um leitor simples: não implementa
aspas especiais, escapes do formato, seções, expansão de variáveis ou INI completo.

## Conversões e configurações

`padrao/conversoes.rts` oferece `inteiro_de_texto(emprestimo[texto])` e
`texto_de_inteiro(inteiro)`, com retornos `resultado[inteiro]` e `resultado[texto]`.
A leitura exige decimal ASCII `[+-]?[0-9]+`, sem aparar espaços implicitamente,
e verifica todo o intervalo de 64 bits. Códigos: 1 vazio, 2 formato inválido,
3 fora do intervalo; formato inválido prevalece sobre excesso de dígitos.
A escrita produz decimal canônico e propaga o contrato do conversor UTF-8.

`padrao/configuracoes.rts` interpreta linhas `chave=inteiro`, devolvendo
`resultado[EntradaNumerica]`, com chave própria e indicação de linha ignorada.
Linhas vazias e comentários de linha `#` são ignorados; esquema, repetições e
armazenamento ficam a cargo do chamador. [Contrato da 0.42U](CONVERSOES_E_CONFIGURACOES_RS_0_42U.md).

## Erros, execução e evolução

Erros de compilação informam origem quando disponível. Falhas aritméticas,
índices inválidos, dono inativo e falta de memória podem encerrar o programa.
`resultado[T]` não captura automaticamente essas falhas. APIs recuperáveis
precisam ser usadas explicitamente; não há tratamento geral `try/catch`.

A implementação de desenvolvimento é Python e emite PE/ELF x86-64 diretamente;
o executável RS não depende de Python. O0–O8 selecionam transformações conforme
o corpo e os recursos suportados; usar O8 não promete execução mais rápida.
A [0.42S](FUNCOES_MISTAS_RS_0_42S.md) permite funções escalares otimizadas
junto de corpos conservadores. Registros/donos/arquivos ainda não têm IR comum.

RS é um projeto próprio. Vocabulário compartilhado com Portugol e outros
projetos não implica compatibilidade sintática ou binária. O objetivo de
autocompilação em RS permanece gradual; a migração de AST/front-end precisa
preservar essa especificação e demonstrar equivalência antes da integração.
