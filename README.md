# RoteiroSimples (RS) — versão experimental 0.25

**Linguagem de programação em português brasileiro** com compilador de desenvolvimento
em Python 3.10+ que gera diretamente executáveis nativos x86-64 Windows (PE32+) e Linux
(ELF64), sem etapa intermediária obrigatória em C, LLVM ou montador externo. Os
executáveis gerados **não dependem do Python**. Projeto experimental: **não usar em produção**.

> **Decisão linguística:** palavras reservadas, nomes de variáveis, tipos, funções e caminhos
> que controlamos seguem o português brasileiro e não levam acentos na sintaxe.
> Mensagens, comentários e textos exibidos aceitam acentuação e UTF-8 normalmente.
> Alguns nomes de arquivos e argumentos históricos foram mantidos por compatibilidade.

## Novo na RS 0.25 — dados compostos em funções

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

O tamanho da lista e a capacidade do buffer fazem parte do tipo: `texto[16]` não é intercambiável com `texto[32]`. As funções podem usar `copie`, `junte` e `limpe` em seus buffers locais e parâmetros; a leitura `leia` dentro de funções permanece indisponível. O resultado de função que devolve um valor composto precisa de destino explícito; armazene-o em variável antes de passá-lo a outra função. Registros aninhados e listas dinâmicas ainda não foram implementados.

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
[`exemplos/funcoes_compostas.rts`](exemplos/registros_recursao.rts).

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

### Limitações históricas da RS 0.24 (superadas parcialmente na 0.25)

Na RS 0.24 ainda não havia retorno de registros inteiros nem passagem de listas e buffers às funções. Esses dois recursos foram adicionados na RS 0.25. Ainda não há registros aninhados, campos do tipo texto ou lista, empréstimos de referências,
alocação dinâmica, ponteiros brutos ou funções que recebam textos. O controle de pilha
não substitui um sistema completo de segurança de memória nem uma auditoria do código
nativo. Não se promete segurança para aplicações de produção.

## Começar no Windows

1. Instale Python 3.10 ou posterior e confirme `py -3 --version`.
2. Baixe ou clone este repositório e extraia o pacote em uma pasta.
3. Execute **`INICIAR_RS.bat`** e escolha **1** para compilar e executar a demonstração
   de registros e recursão. A opção **2** abre o mesmo exemplo no Bloco de Notas.
4. Para executar os testes, escolha **3**.

Via PowerShell:

```powershell
py -3 compilar.py exemplos\registros_recursao.rts --alvo windows -O 8 -o roteiro_windows.exe
.\roteiro_windows.exe
py -3 -m unittest discover -s testes -v
```

## Compilar no Linux

Requer sistema Linux e processador x86-64:

```bash
python3 compilar.py exemplos/registros_recursao.rts --alvo linux -O 8 -o roteiro_linux
./roteiro_linux
python3 -m unittest discover -s testes -v
```

O compilador aceita os níveis históricos de otimização **`-O 0` até `-O 8`**;
nenhum nível foi criado na RS 0.24. Para programas com escopos locais,
funções ou registros, a geração conservadora prevalece para evitar transformações
que ainda não compreendem chamadas e identidades de valores compostos.

## Recursos presentes até a RS 0.24

| Recurso | Situação |
|---|---|
| Inteiros de 64 bits, lógicos, expressões e erros aritméticos | Implementado |
| `escreva`, `leia`, condições, `enquanto`, `para`, `pare` e `continue` | Implementado |
| Escopos léxicos e ocultação de nomes locais | Implementado desde 0.23 |
| Funções, parâmetros e retornos numéricos e lógicos | Implementado desde 0.23 |
| Tipos compostos com campos escalares e passagem por valor | **Novo na 0.24** |
| Recursão direta e indireta com orçamento de pilha | **Novo na 0.24** |
| Listas fixas com índices verificados e buffers de texto UTF-8 | Implementado |
| Memória dimensionada para quadros locais, sondagem de páginas | Implementado |
| Representação intermediária tipada, fluxo de controle, versões únicas, memória versionada | Implementado para a parte já suportada da linguagem |
| Análises avançadas em funções e registros | Ainda não |
| Tipos reais/decimais, módulos, dados dinâmicos, referências e empréstimos | Ainda não |

## Organização atual

- `compilador/`: léxico, análise sintática, escopos, tipos, representação intermediária
  e análises de fluxo.
- `backend/`: emissão direta de instruções x86-64 e geração de PE/ELF.
- `bibliotecas/`: operações matemáticas atualmente suportadas.
- `exemplos/`: programas `.rts`, inclusive a demonstração nova.
- `testes/`: verificações estáticas, execução dos executáveis e regressões.
- `docs/`: notas da arquitetura e [histórico do README até a RS 0.23](docs/HISTORICO_README_ATE_RS_0_23.md).
- `sintaxe.py`, `codigo_nativo.py` e `ir.py`: interfaces antigas conservadas por compatibilidade.

## Próximas prioridades

**RS 0.25:** suportar retornos de registros por valor, registros aninhados e
passagem segura de listas e textos às funções, com regras explícitas de propriedade.
Depois: sistema de módulos, tipos reais com semântica de precisão definida,
memória dinâmica, referências emprestadas e análise de fluxo entre funções.

Ainda não foi escolhida uma licença para publicação do código.
