# RoteiroSimples (RS) — versão experimental 0.37

**Linguagem de programação em português brasileiro** com compilador de desenvolvimento
em Python 3.10+ que gera diretamente executáveis nativos x86-64 Windows (PE32+) e Linux
(ELF64), sem etapa intermediária obrigatória em C, LLVM ou montador externo. Os
executáveis gerados **não dependem do Python**. Projeto experimental: **não usar em produção**.

> **Decisão linguística:** palavras reservadas, nomes de variáveis, tipos, funções e caminhos
> que controlamos seguem o português brasileiro e não levam acentos na sintaxe.
> Mensagens, comentários e textos exibidos aceitam acentuação e UTF-8 normalmente.
> Alguns nomes de arquivos e argumentos históricos foram mantidos por compatibilidade.

## RS 0.37 — bytes seguros, persistência binária e saída de processo

A RS agora possui **`bytes[N]`**, um tipo de buffer binário separado
de `texto[N]`, com comprimento dinâmico e capacidade fixa verificada:

```text
inicio {
    seja dados: bytes[10]
    adicione_byte(dados, 82)
    adicione_byte(dados, 83)
    dados[1] = 255
    escreva(dados[1])
    escreva(tamanho(dados))
    encerre(0)
}
```

- `adicione_byte(destino, valor)`: anexa um inteiro na faixa 0 a 255,
  recusando ultrapassar a capacidade.
- `dados[indice]`: somente índices menores que `tamanho(dados)`
  podem ser lidos ou sobrescritos; sobrescrever não aumenta o tamanho.
- `limpe(dados)`: redefine o comprimento a zero (não apaga
  necessariamente todos os bytes da memória).
- `carregue_trecho` e `grave_trecho`: agora aceitam `bytes[N]` além
  dos buffers `texto[N]` legados; não convertem em UTF-8.
- `encerre(codigo)`: devolve ao sistema um código entre 0 e 255.
  Valores fora desse intervalo são rejeitados durante a execução.

O projeto continua experimental. A RS **não garante gravação atômica,
durabilidade após desligamento nem isolamento de transações**; também não
possui ainda drivers PostgreSQL, SQLite ou MariaDB.

Veja a [especificação RS 0.37](docs/BYTES_E_SAIDA_RS_0_37.md) e
[o exemplo de cabeçalho binário](exemplos/aplicacoes/criar_cabecalho_binario.rts).

## RS 0.36 — consolidação e aplicações de referência

A RS 0.36 **não introduz outro nível de otimização**. Ela consolida a escolha
entre o gerador conservador, a representação intermediária tipada e o
backend SSA. A escolha agora vem de uma mesma decisão no compilador e
na opção pública `--mostrar-estrategia`. Assim, um programa com
funções, registros, listas dinâmicas ou arquivos nativos não é apresentado
falsamente como otimizado via SSA só por ter sido compilado com `-O 8`.

```bash
python compilar.py exemplos/aplicacoes/analisar_entregas.rts --alvo linux -O 8 --mostrar-estrategia -o entregas
```

Há **duas aplicações executáveis escritas integralmente em RS**:

- [Copiador binário em blocos de 4096 bytes](exemplos/aplicacoes/copiar_arquivo_em_blocos.rts):
  lê `origem.bin` e cria `copia.bin`, preservando dados arbitrários,
  inclusive arquivos vazios; informa falhas recuperáveis de leitura/gravação.
  Por segurança, recusa um destino que já exista, pois a RS ainda não
  dispõe de truncamento atômico; nomes são literais por enquanto.
- [Analisador de 150 entregas](exemplos/aplicacoes/analisar_entregas.rts):
  utiliza listas dinâmicas tipadas, registros, empréstimos e funções para
  calcular quantidade e receita em centavos. **Este programa é apenas
  em memória**; persistência estruturada será uma etapa posterior.

[Documentação da RS 0.36 e matriz O0–O8](docs/CONSOLIDACAO_RS_0_36.md).
Os testes executam os binários nativos, com resultados e arquivos
conferidos independentemente, e não apenas comparam fontes ou ASTs.

## RS 0.35 — acesso binário posicional

Dois comandos permitem modificar partes de arquivos sem truncar o conteúdo
e recuperar resultados de I/O sem encerrar o programa:

```text
inicio {
    seja pagina: texto[100]
    seja estado = 0
    copie(pagina, "Entrega 101")
    grave_trecho("banco.rsd", pagina, 4096, estado)
    carregue_trecho("banco.rsd", pagina, 4096, 11, estado)
    escreva(estado)
}
```

`estado` recebe a quantidade de bytes processados (`0` inclusive no EOF)
ou códigos negativos para falha de abertura, operação, parâmetros e
fechamento. Os dados são bytes arbitrários, embora o armazenamento inicial
ainda seja `texto[N]`. A gravação não é atômica nem durável após quedas de
energia; sincronização e transações permanecem pendentes.

Veja [a especificação das operações](docs/ARQUIVOS_POSICIONAIS_RS_0_35.md)
e [o exemplo executável](exemplos/arquivos_posicionais.rts).

## RS 0.34 — persistência nativa de arquivos (experimental)

Dois comandos permitem salvar e carregar os bytes de um buffer `texto[N]`
sem depender de Python na execução:

```text
inicio {
    seja registro: texto[100]
    copie(registro, "entrega 101, concluida")
    grave_arquivo("entregas.txt", registro)

    limpe(registro)
    carregue_arquivo("entregas.txt", registro)
    escreva(registro)
}
```

`grave_arquivo` cria ou substitui o arquivo, gravando exatamente o comprimento
atual do texto, sem acrescentar quebra de linha. `carregue_arquivo` lê todo o
arquivo, substituindo os bytes e o comprimento do buffer; se o arquivo for
maior do que a capacidade, encerra o programa com erro, sem cortar dados
silenciosamente. Falhas de abertura, leitura, gravação e fechamento também
geram erro. Nomes de arquivo são literais relativos, ASCII e sem segmentos
`..`, por enquanto; os diretórios intermediários precisam existir.

Esses recursos operam sobre conteúdo em bytes (não serializam registros).
Veja [o guia da RS 0.34](docs/ARQUIVOS_RS_0_34.md) e
[o exemplo de persistência](exemplos/persistencia_texto.rts).

## RS 0.33 — transferência de propriedade e duração por escopo

A RS agora implementa `mova(destino, origem)` para `lista[]`. A operação
libera o antigo destino, transfere o armazenamento da origem **sem copiar
elementos** e invalida a origem. Usá-la novamente sem outra transferência
causa um erro controlado.

Listas dinâmicas podem ser declaradas em blocos `se`, `enquanto` e
`para`. A saída normal, `pare` e `continue` liberam as listas locais;
`retorne` libera os descritores ativos da função, mesmo que existam
declarações não alcançadas.

```text
inicio {
    seja principal: lista[]
    para i de 1 ate 4 {
        seja temporaria: lista[]
        adicione(temporaria, i * 10)
        se i == 4 {
            mova(principal, temporaria)
        }
    }
    escreva(principal[0])
}
```

**Saída esperada:** `40`.

### Empréstimo explícito e temporário, somente para leitura

Funções podem receber `emprestimo[lista]` usando `empreste(lista)`, sem
copiar os elementos nem adquirir a propriedade. Na função, são permitidas
consultas por índice, `tamanho` e `capacidade`. O empréstimo pode ser
repassado a outra função, mas nunca retornado, guardado em outra variável,
reatribuído ou utilizado para alterar/liberar a lista.

```text
funcao total(valores: emprestimo[lista]) -> inteiro {
    seja soma = 0
    para i de 0 ate tamanho(valores) - 1 {
        soma = soma + valores[i]
    }
    retorne soma
}
inicio {
    seja vendas: lista[]
    adicione(vendas, 12)
    adicione(vendas, 18)
    escreva(total(empreste(vendas)))
    escreva(vendas[0])
}
```

**Saída esperada:** `30` e `12`. O compilador impede a saída de referências
emprestadas do contexto da chamada; a validade da lista original também é
verificada em tempo de execução.

Listas dinâmicas agora aceitam `lista[inteiro]` e `lista[logico]`
(além do legado `lista[]` como inteiro). O empréstimo preserva o tipo:
`emprestimo[lista[logico]]`, por exemplo. Transferências entre listas
de tipos diferentes são erros de compilação. Registros declarados com `tipo` também podem ser elementos de
`lista[Registro]`. O armazenamento cresce com a largura real do registro,
inclusive campos aninhados, e permite `adicione(lista, registro)`,
`lista[indice] = registro`, cópias por valor com
`seja copia: Registro = lista[indice]` e empréstimos somente para leitura.
Um índice não cria uma referência prolongada ao elemento; a leitura
de um registro produz uma cópia independente. Ainda não é possível
editar campos diretamente como `lista[indice].campo`. Textos dinâmicos
e tipos arbitrários compostos permanecem em planejamento.
A RS permanece experimental. Leia
[`docs/PROPRIEDADE_E_ESCOPOS_RS_0_33.md`](docs/PROPRIEDADE_E_ESCOPOS_RS_0_33.md)
e o [guia de listas tipadas](docs/LISTAS_TIPADAS_RS_0_33.md), com o
[exemplo de entregas](exemplos/entregas_tipadas.rts).

## Histórico: RS 0.32 — listas dinâmicas e propriedade exclusiva

A linguagem agora reconhece **lista[]**, com armazenamento nativo que cresce conforme os dados são adicionados e é liberado automaticamente no fim da função ou do programa proprietário.

```text
inicio {
    seja pedidos: lista[]
    adicione(pedidos, 10)
    adicione(pedidos, 20)

    escreva(tamanho(pedidos))
    escreva(pedidos[1])

    remova_ultimo(pedidos)
    escreva(tamanho(pedidos))
}
```

**Saída:** 2, 20 e 1, cada um em uma linha.

As operações incluem `adicione`, `remova_ultimo`, `limpe_lista`, `libere`, `tamanho`, `capacidade` e índices verificados para leitura e escrita. O gerador usa `mmap/munmap` no Linux e `VirtualAlloc/VirtualFree` no Windows. A lista inicia com zero posições e cresce conforme necessário, sem um tamanho fixo declarado no código RS.

**Propriedade única:** nesta etapa, cada lista dinâmica pertence a um único escopo de função ou `inicio`. Não é possível copiá-la, passá-la como argumento, retorná-la ou armazená-la em registros. Declarações em condicionais ou laços também continuam restritas enquanto o gerenciamento completo de pontos de saída estiver em construção. Isso evita referências pendentes e liberações duplicadas. A liberação explícita torna a lista inutilizável, com erro controlado em acessos posteriores; listas sem liberação explícita são liberadas ao final do proprietário.

**Exemplo:** [`exemplos/listas_dinamicas.rts`](exemplos/listas_dinamicas.rts). Veja as [regras completas de propriedade, segurança e limitações](docs/LISTAS_DINAMICAS_RS_0_32.md). As listas fixas `lista[N]`, os resultados tipados e os níveis de otimização de `-O 0` a `-O 8` continuam disponíveis. Nenhum novo nível de otimização foi criado.

## Histórico: RS 0.31 — resultados genéricos e propagação de falhas

O sistema de tipos agora aceita **resultado[T]**, especializado na compilação para
cada tipo concreto utilizado, inclusive **inteiros, lógicos, registros, textos e listas fixas**.

```text
funcao dividir(a: inteiro, b: inteiro) -> resultado[inteiro] {
    se b == 0 {
        retorne falha[inteiro](1)
    }
    retorne sucesso[inteiro](a / b)
}

funcao calcular(n: inteiro) -> resultado[inteiro] {
    seja parte = dividir(n, 2)
    propague parte
    retorne sucesso[inteiro](parte.valor + 5)
}

inicio {
    seja resposta = calcular(20)
    escreva(resposta.valido)
    escreva(resposta.valor)
}
```

**Resultado:** 1 e 15, um por linha.

- **resultado[T]** possui campos `valido`, `valor` e `codigo_erro`.
- **sucesso[T](valor)** constrói um resultado válido.
- **falha[T](codigo)** constrói um resultado inválido, com valor inicializado.
- **propague nome** encaminha o erro de uma variável de resultado para a função atual quando `valido` é falso. Funciona apenas em funções com retorno `resultado[T]` e exige nome de variável explícito.
- Tipos compostos e capacidades são conferidos estaticamente. **resultado[inteiro] e resultado[logico] são tipos diferentes**; não há conversão implícita.
- Os registros da Biblioteca Padrão RS 0.30 continuam disponíveis e não são automaticamente convertidos para os novos resultados genéricos.

**Escopo real:** o recurso é uma *especialização estática*, não uma implementação de funções genéricas arbitrárias ou exceções. Transbordamentos nativos e falhas de índices continuam encerrando a execução conforme a proteção anterior — `propague` não os captura.

**Exemplo novo:** [`exemplos/resultados_genericos.rts`](exemplos/resultados_genericos.rts). Veja a [documentação completa e limitações](docs/RESULTADOS_GENERICOS_RS_0_31.md). Nenhum nível de otimização foi acrescentado.

## Histórico: RS 0.30 — resultados tipados e erros explícitos

A Biblioteca Padrão agora fornece dois **tipos de resultado**: `ResultadoInteiro` e `ResultadoLogico`. Cada um possui `valido`, `valor` e `codigo_erro`. São registros realmente implementados em `.rts`; a linguagem verifica os tipos na compilação e copia os resultados por valor, sem depender de Python na execução.

```text
importe "padrao/resultados.rts" como resultados
importe "padrao/matematica_segura.rts" como segura

inicio {
    seja divisao: resultados.ResultadoInteiro = segura.dividir(10, 0)

    se divisao.valido {
        escreva(divisao.valor)
    } senao {
        escreva("Falha de divisao detectada")
        escreva(divisao.codigo_erro)
    }

    seja raiz: resultados.ResultadoInteiro = segura.raiz_quadrada_inteira(81)
    escreva(resultados.inteiro_ou(raiz, -1))
}
```

**Saída:** `Falha de divisao detectada`, `1` e `9`, em linhas separadas.

O módulo `padrao/resultados.rts` contém os construtores de sucesso e falha, dois tipos de resultado, funções de consulta com valor alternativo e os códigos padronizados. `padrao/matematica_segura.rts` disponibiliza **dez operações com verificação explícita de domínio**: `dividir`, `resto`, `fatorial`, `fibonacci`, `mdc`, `mmc`, `potencia_natural`, `raiz_quadrada_inteira`, `eh_primo` e `limitar`.

**Limitação importante:** são registros tipados da Biblioteca Padrão, **não** um tipo genérico embutido `resultado[T]`. Erros de domínio conhecidos são devolvidos como valores; **transbordamentos em multiplicações gerais ainda podem encerrar o executável**. As funções antigas com retornos convencionais continuam disponíveis para não quebrar programas anteriores. A RS 0.30 não introduziu um novo nível de otimização.

**Exemplo completo:** [`exemplos/resultados_tipados.rts`](exemplos/resultados_tipados.rts). Consulte a [documentação de resultados e códigos de erro](docs/RESULTADOS_TIPADOS_RS_0_30.md).

## Histórico: RS 0.29 — Biblioteca Padrão escrita em RoteiroSimples

A primeira Biblioteca Padrão oficial está em **`biblioteca_padrao/`**, com **30 funções reais** implementadas em arquivos `.rts`, organizadas em quatro módulos: `numeros` (9), `matematica` (8), `estatistica` (6) e `listas` (7).

```text
importe "padrao/numeros.rts" como numeros
importe "padrao/matematica.rts" como matematica
importe "padrao/estatistica.rts" como estatistica
importe "padrao/listas.rts" como listas

inicio {
    seja valores: lista[5]
    valores[0] = 8
    valores[1] = 3
    valores[2] = 8
    valores[3] = -2
    valores[4] = 5

    escreva(numeros.absoluto(-25))
    escreva(matematica.fatorial(5))
    escreva(estatistica.media_cinco(valores))
    seja ordenados: lista[5] = listas.ordenar_cinco(valores)
    escreva(ordenados[0])
}
```

**Resultado:** `25`, `120`, `4` e `-2`, cada um em uma linha.

`padrao/` é um prefixo especial: o compilador localiza sua biblioteca instalada, mesmo quando o programa do usuário está em outra pasta. Os módulos são resolvidos na compilação, incorporados ao executável nativo e não precisam existir ao lado do programa executável. Importações próprias ainda são relativas ao projeto e mantêm a proteção contra fuga de diretórios.

**Escopo honesto:** estatística e listas trabalham, por ora, com `lista[5]`; não temos listas dinâmicas ou tipos genéricos. Os resultados são inteiros de 64 bits, com verificações de transbordamento. `fatorial` só atende 0 a 20 e devolve `-1` fora dessa faixa; expoente negativo de `potencia_natural` devolve `0`, como convenção provisória. Essas regras e as demais pré-condições estão no [manual completo da Biblioteca Padrão](docs/BIBLIOTECA_PADRAO_RS_0_29.md).

**Exemplo executável:** [`exemplos/biblioteca_padrao.rts`](exemplos/biblioteca_padrao.rts). Os níveis existentes de `-O 0` a `-O 8` foram mantidos, sem criar outro. A Biblioteca Padrão é escrita na linguagem RS; o Python continua necessário apenas para executar o compilador de desenvolvimento.

## Histórico: RS 0.28 — espaços de nomes e visibilidade

Podemos usar funções e tipos com nomes iguais em módulos diferentes, graças à importação com apelido:

```text
// principal.rts
importe "financeiro.rts" como financeiro
importe "estoque.rts" como estoque

inicio {
    seja pedido: financeiro.Pedido
    pedido.valor = 25
    escreva(financeiro.calcular(pedido))
}
```

No módulo `financeiro.rts`, utilizamos `publico funcao calcular(...)` para permitir a chamada pelo importador e `privado funcao acrescentar_taxa(...)` para proteger uma função de uso interno. Isso também funciona com declarações de `tipo`.

- **`publico`** deixa a definição acessível para quem importar o módulo.
- **`privado`** impede o acesso externo, sem impedir chamadas dentro do próprio módulo.
- Declarações sem modificador permanecem públicas para preservar os programas anteriores.
- **`importe "arquivo.rts" como apelido`** exige nomes qualificados (`apelido.funcao`, `apelido.Tipo`); a forma anterior sem apelido continua funcionando.
- Módulos importados duas vezes não são duplicados; nomes e tipos internos de arquivos distintos permanecem separados.
- Erros de conflito, acesso privado, nome inexistente e dependência circular são diagnosticados na compilação.

**Exemplo executável:** [`exemplos/espacos_nomes/principal.rts`](exemplos/espacos_nomes/principal.rts), com dois tipos `Pedido` e duas funções `calcular`. Saída: `RS 0.28: espacos de nomes`, `30` e `50`.

Consulte a [especificação dos espaços de nomes](docs/ESPACOS_DE_NOMES_RS_0_28.md). Mantivemos os níveis de `-O 0` a `-O 8`; não criamos outro nível de otimização.

## Histórico: RS 0.27 — sistema de módulos em português

Agora podemos organizar um projeto em **vários arquivos `.rts`**, reutilizando tipos e funções próprias com o comando `importe`:

```text
// exemplos/modulos/valores.rts
funcao acrescentar_taxa(valor: inteiro) -> inteiro {
    retorne valor + 5
}
```

```text
// exemplos/modulos/pedidos.rts
importe "valores.rts"
tipo Pedido {
    preco: inteiro
    quantidade: inteiro
}
funcao calcular_pedido(pedido: Pedido) -> inteiro {
    retorne acrescentar_taxa(pedido.preco * pedido.quantidade)
}
```

```text
// exemplos/projeto_modulos.rts
importe "modulos/pedidos.rts"
inicio {
    seja pedido: Pedido
    pedido.preco = 25
    pedido.quantidade = 4
    escreva(calcular_pedido(pedido))
}
```

**Resultado:** `105`. O compilador resolve as dependências, reúne os arquivos e gera um único executável Windows ou Linux, sem carregar módulos durante a execução.

A importação usa caminho relativo ao arquivo que importa; apenas arquivos `.rts` dentro da pasta do projeto são aceitos. Importações repetidas são reunidas uma única vez, dependências circulares e nomes duplicados geram erros. Na RS 0.27 todos os tipos e funções compartilhavam o mesmo espaço global. A RS 0.28 adicionou apelidos, qualificadores e elementos privados.

**Exemplo:** [`exemplos/projeto_modulos.rts`](exemplos/projeto_modulos.rts). Veja [a documentação completa dos módulos](docs/MODULOS_RS_0_27.md). O parâmetro `--mostrar-modulos` mostra os arquivos carregados. Os níveis de otimização continuam de `-O 0` a `-O 8`, sem acrescentar outro nível.

## Histórico: RS 0.26 — registros aninhados e chamadas compostas diretas

Registros podem conter outros registros, listas de inteiros e buffers UTF-8 de capacidade declarada. Os campos são acessados por caminhos completos e verificados na compilação.

```text
tipo Endereco {
    numero: inteiro
    rua: texto[24]
}
tipo Cliente {
    endereco: Endereco
    notas: lista[3]
}
funcao criar_cliente(numero: inteiro) -> Cliente {
    seja cliente: Cliente
    cliente.endereco.numero = numero
    copie(cliente.endereco.rua, "Rua Mineira")
    cliente.notas[0] = 12
    cliente.notas[1] = 18
    retorne cliente
}
funcao calcular(cliente: Cliente) -> inteiro {
    retorne cliente.endereco.numero + cliente.notas[0] + cliente.notas[1]
}
inicio {
    escreva(calcular(criar_cliente(70)))
}
```

**Saída:** `100`.

Além dos registros aninhados, agora é possível passar diretamente o resultado composto de uma função como argumento de outra, como `calcular(criar_cliente(70))`. O compilador cria uma região temporária local para o resultado intermediário e preserva a avaliação da esquerda para a direita. Cópias de registros, listas e textos permanecem **por valor**, sem compartilhamento implícito de memória. Tamanhos e capacidades continuam fazendo parte dos tipos.

Registros são declarados em ordem: quando um campo utiliza um tipo próprio, esse tipo deve ter sido declarado anteriormente. Não há tipos recursivos por valor (que teriam tamanho infinito), memória dinâmica ou referências emprestadas nesta versão. Não criamos novos níveis de otimização.

**Exemplo:** [`exemplos/registros_aninhados.rts`](exemplos/registros_aninhados.rts). Detalhes em [`docs/REGISTROS_ANINHADOS_RS_0_26.md`](docs/REGISTROS_ANINHADOS_RS_0_26.md).

## Histórico: RS 0.25 — dados compostos em funções

A linguagem agora permite passar e devolver **registros, listas de inteiros e buffers UTF-8 por valor**, com cópias independentes entre o chamador e a função.

```text
tipo Produto {
    preco: inteiro
    quantidade: inteiro
}
funcao novo_produto(valor: inteiro) -> Produto {
    seja p: Produto
    p.preco = valor
    p.quantidade = 4
    retorne p
}
funcao quadrados() -> lista[3] {
    seja numeros: lista[3]
    numeros[0] = 1
    numeros[1] = 4
    numeros[2] = 9
    retorne numeros
}
inicio {
    seja p: Produto = novo_produto(25)
    seja valores: lista[3] = quadrados()
    escreva(p.preco * p.quantidade)
    escreva(valores[2])
}
```

**Resultado:** `100` e `9`, cada um em uma linha.

O tamanho da lista e a capacidade do buffer fazem parte do tipo: `texto[16]` não é intercambiável com `texto[32]`. As funções podem usar `copie`, `junte` e `limpe` em seus buffers locais e parâmetros; a leitura `leia` dentro de funções permanece indisponível. O resultado de função que devolve um valor composto precisa de destino explícito; armazene-o em variável antes de passá-lo a outra função. Na RS 0.25, registros aninhados e passagem direta de resultados compostos como argumentos ainda não estavam disponíveis; ambos foram introduzidos na RS 0.26. Listas dinâmicas permanecem pendentes.

**Exemplo executável:** [`exemplos/funcoes_compostas.rts`](exemplos/funcoes_compostas.rts). Veja a [especificação da RS 0.25](docs/FUNCOES_COMPOSTAS_RS_0_25.md). Mantivemos os níveis históricos de `-O 0` a `-O 8`; não adicionamos outro nível.

## Histórico: RS 0.24 — registros e recursão controlada

Esta atualização prioriza **fundamentos de linguagem**, não outro nível de otimização.
Agora o programador pode declarar um tipo composto por campos `inteiro` e `logico`,
criar registros, ler e alterar seus campos e enviá-los **por valor** a funções nativas.
Chamadas recursivas diretas e indiretas têm proteção contra esgotamento do orçamento
de pilha do trecho recursivo.

```text
tipo Pedido {
    preco: inteiro
    quantidade: inteiro
    ativo: logico
}

funcao calcular(pedido: Pedido) -> inteiro {
    se pedido.ativo {
        retorne pedido.preco * pedido.quantidade
    } senao {
        retorne 0
    }
}

funcao fatorial(n: inteiro) -> inteiro {
    se n <= 1 {
        retorne 1
    } senao {
        retorne n * fatorial(n - 1)
    }
}

inicio {
    seja pedido: Pedido
    pedido.preco = 25
    pedido.quantidade = 4
    pedido.ativo = verdadeiro
    escreva(calcular(pedido))
    escreva(fatorial(5))
}
```

**Saída esperada:** `100` e `120`, um em cada linha. Arquivo completo:
[`exemplos/registros_recursao.rts`](exemplos/registros_recursao.rts).

### Regras dos registros e funções

- `tipo Nome { ... }`: os campos têm nome próprio e tipo `inteiro` ou `logico`.
  Cada campo usa um espaço de 8 bytes; definições de tipos antecedem funções e `inicio`.
- `seja registro: Nome`: cria um registro local, com os campos zerados.
  O acesso `registro.campo` verifica nome e tipo na compilação.
- Um parâmetro `pedido: Pedido` recebe **cópia independente** dos campos.
  Uma alteração dentro da função não altera o valor do chamador.
- Funções podem chamar outras funções e chamar a si mesmas. Argumentos e
  retornos são tipados; os retornos ainda aceitam somente `inteiro` ou `logico`.
- Na parte recursiva da execução, o compilador controla um orçamento acumulado
  de pilha de **1 MiB** e encerra com diagnóstico e código 1 quando ele é excedido,
  antes de reservar o quadro recursivo seguinte. A sondagem de páginas para grandes
  quadros locais continua disponível. Esse limite de segurança não é um máximo
  geral de variáveis, listas, buffers ou tamanho de executável.
- Nesta versão o gerador de código conservador executa funções e registros; as
  análises avançadas de atribuição única e otimização de memória ainda não são
  aplicadas a programas que usam esses novos recursos.

### Limitações históricas da RS 0.24 (superadas parcialmente nas versões seguintes)

Na RS 0.24 ainda não havia retorno de registros inteiros nem passagem de listas e buffers às funções. Esses recursos chegaram na RS 0.25; registros aninhados e campos compostos, na RS 0.26. Ainda não há empréstimos de referências,
alocação dinâmica, ponteiros brutos ou funções que recebam textos. O controle de pilha
não substitui um sistema completo de segurança de memória nem uma auditoria do código
nativo. Não se promete segurança para aplicações de produção.

## Começar no Windows

1. Instale Python 3.10 ou posterior e confirme `py -3 --version`.
2. Baixe ou clone este repositório e extraia o pacote em uma pasta.
3. Execute **`INICIAR_RS.bat`** e escolha **1** para compilar e executar a demonstração
   das listas dinâmicas da RS 0.32. A opção **2** abre o mesmo exemplo no Bloco de Notas.
4. Para executar os testes, escolha **3**.

Via PowerShell:

```powershell
py -3 compilar.py exemplos\listas_dinamicas.rts --alvo windows -O 8 -o roteiro_windows.exe
.\roteiro_windows.exe
py -3 -m unittest discover -s testes -v
```

## Compilar no Linux

Requer sistema Linux e processador x86-64:

```bash
python3 compilar.py exemplos/listas_dinamicas.rts --alvo linux -O 8 -o roteiro_linux
./roteiro_linux
python3 -m unittest discover -s testes -v
```

O compilador aceita os níveis históricos de otimização **`-O 0` até `-O 8`**;
nenhum nível foi criado na RS 0.29. Para programas com escopos locais,
funções ou registros, a geração conservadora prevalece para evitar transformações
que ainda não compreendem chamadas e identidades de valores compostos.

## Recursos presentes até a RS 0.37

| Recurso | Situação |
|---|---|
| Inteiros de 64 bits, lógicos, expressões e erros aritméticos | Implementado |
| `escreva`, `leia`, condições, `enquanto`, `para`, `pare` e `continue` | Implementado |
| Escopos léxicos e ocultação de nomes locais | Implementado desde 0.23 |
| Funções, parâmetros e retornos numéricos e lógicos | Implementado desde 0.23 |
| Tipos compostos com campos escalares e passagem por valor | Implementado desde 0.24 |
| Recursão direta e indireta com orçamento de pilha | Implementado desde 0.24 |
| Listas fixas com índices verificados e buffers de texto UTF-8 | Implementado |
| Memória dimensionada para quadros locais, sondagem de páginas | Implementado |
| Representação intermediária tipada, fluxo de controle, versões únicas, memória versionada | Implementado para a parte já suportada da linguagem |
| Registros aninhados, campos de listas e texto | Implementado na 0.26 |
| Importação de módulos e resolução de dependências | Implementado na 0.27 |
| Espaços de nomes com apelidos e visibilidade pública/privada | Implementado na 0.28 |
| Biblioteca Padrão RS escrita em .rts, 30 funções em quatro módulos | Implementado na 0.29 |
| Resultados tipados e operações matemáticas com erro explícito | Implementado na 0.30 |
| resultado[T], sucesso[T], falha[T] e propague | Implementado na 0.31 |
| `lista[]` e proprietário exclusivo com liberação automática | Implementado na 0.32 |
| Transferência `mova`, limpeza por escopo, empréstimo imutável | Implementado na 0.33 |
| Listas dinâmicas tipadas para inteiros, lógicos e registros | Implementado na 0.33 |
| Leitura e gravação de arquivos inteiros | Implementado na 0.34 |
| Leitura e gravação binária por posição, com estado de erro recuperável | Implementado na 0.35 |
| Tipo `bytes[N]`, limites binários e `encerre(codigo)` | Implementado na 0.37 |
| Passagem direta de resultados compostos a outras funções | Implementado na 0.26 |
| Análises avançadas em funções e registros | Ainda não |
| Tipos reais/decimais, textos dinâmicos, empréstimos mutáveis, FFI e durabilidade de arquivos | Ainda não |

## Organização atual

- `compilador/`: léxico, análise sintática, escopos, tipos, representação intermediária
  e análises de fluxo.
- `backend/`: emissão direta de instruções x86-64 e geração de PE/ELF.
- `biblioteca_padrao/`: funções oficiais em módulos `.rts`, incluindo números, matemática, estatística, listas e resultados tipados.
- `backend/listas_dinamicas.py`: gerador de alocação e liberação nativas das listas de propriedade exclusiva.
- `bibliotecas/`: compatibilidade com antigas operações matemáticas internas.
- `exemplos/`: programas `.rts`, inclusive a demonstração nova.
- `testes/`: verificações estáticas, execução dos executáveis e regressões.
- `docs/`: notas da arquitetura e [histórico do README até a RS 0.23](docs/HISTORICO_README_ATE_RS_0_23.md).
- `sintaxe.py`, `codigo_nativo.py` e `ir.py`: interfaces antigas conservadas por compatibilidade.

## Próximas prioridades

**RS 0.38 (planejamento):** identificadores de arquivo seguros, tratamento de erros tipados, sincronização durável (`fsync` e `FlushFileBuffers`) e políticas de acesso concorrente. O tipo `bytes[N]` foi introduzido na RS 0.37. Continuam pendentes a alocação dinâmica de bytes, operações atômicas, travamento e interface para bibliotecas externas; esses fundamentos antecedem o motor Dados RS.

O projeto ainda é experimental, não pronto para produção. Não estamos acrescentando níveis de otimização.

Ainda não foi escolhida uma licença para publicação do código.
