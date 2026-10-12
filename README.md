# RoteiroSimples (RS) — versão experimental 0.7

**RoteiroSimples** é um projeto experimental de linguagem de programação em português brasileiro. O compilador de desenvolvimento está escrito em Python 3.10+ e gera instruções x86-64 diretamente para executáveis Windows (PE32+) e Linux (ELF64), sem passar por C, Rust ou LLVM. Os programas gerados não precisam de Python para executar.

> Estado do projeto: protótipo educacional. Ainda não é seguro para sistemas de produção.

## Novo na RS 0.7: tipos de dados e controle básico da pilha

As palavras reservadas continuam **sem acentos**, como `inicio`, `senao`, `inteiro` e `logico`.

```text
inicio {
    seja idade: inteiro = 17
    seja ativo: logico = verdadeiro
    seja maior = idade >= 18
    escreva(maior)
    se ativo {
        escreva("Está habilitado!")
    }
}
```

- `inteiro` representa números com sinal de 64 bits. `logico` representa `verdadeiro` ou `falso`.
- Pode escrever `seja valor: inteiro = 42` ou deixar a linguagem inferir, como em `seja valor = 42`.
- Comparações inferem `logico`, e o compilador proíbe misturar booleanos e inteiros em expressões incompatíveis. `leia` aceita apenas variáveis `inteiro`.
- Para preservar compatibilidade, `se` e `enquanto` continuam aceitando valores inteiros (zero equivale a falso).
- `escreva(logico)` atualmente imprime `1` ou `0`. Os textos entre aspas continuam aceitando UTF-8 normalmente.
- Cada variável local ocupa 8 bytes na pilha. Impusemos limite provisório de **256 variáveis** até implementar sondagem de pilha (especialmente no Windows).
- Não há ponteiros, heap, listas ou gerenciamento dinâmico de memória. A checagem de tipos é um **primeiro passo**, não uma garantia geral de segurança.
- O compilador rejeita literais inteiros positivos fora do intervalo, mas operações em tempo de execução ainda podem transbordar sem diagnóstico.

**Exemplo novo:** `exemplos/tipos.rts`. Veja [tipos e memória da RS 0.7](docs/TIPOS_E_MEMORIA_RS_0_7.md) para os detalhes e limitações.

## Padrão da RS 0.5: sintaxe sem acentos

**Regra oficial:** comandos, nomes de variáveis e bibliotecas usam apenas caracteres ASCII, como `inicio`, `senao`, `preco` e `matematica`. Não são aceitas grafias acentuadas como código. **Não haverá aliases automáticos** nem normalização Unicode de identificadores nesta fase.

Textos entre aspas, comentários e mensagens de erro continuam em português brasileiro e aceitam UTF-8 normalmente: `escreva("Olá, coração!")`.

**Mudança de compatibilidade:** programas anteriores que continham comandos ou nomes de variáveis com acentos devem trocar essas grafias pela forma sem acentos. Todos os exemplos e testes deste repositório foram atualizados.

## Incluído desde a RS 0.5: repeticao com `para`

A linguagem continua usando **comandos e identificadores sem acentos**. Textos entre aspas e comentarios continuam aceitando portugues brasileiro em UTF-8.

```text
inicio {
    para numero de 1 ate 5 {
        escreva(numero)
    }
    para numero de 5 ate 1 passo -2 {
        escreva(numero)
    }
}
```

`para numero de 1 ate 5` percorre de 1 a 5 **inclusive**, com passo 1 por padrao. `passo -2` permite contagem regressiva. O contador e criado automaticamente caso ainda nao exista e permanece acessivel apos o bloco (ate que exista escopo de blocos). O valor inicial e calculado uma vez; o valor final e recalculado a cada iteracao. O passo precisa ser um inteiro constante diferente de zero; o programa encerra a contagem se o incremento extrapolaria um inteiro de 64 bits. `pare` encerra o laco atual e `continue` executa o incremento antes da proxima iteracao.

Variaveis com `seja` ainda devem ser declaradas fora de blocos `para`, `enquanto` ou `se` nesta versao.

## RS 0.6 — leitura de inteiros e primeiros cuidados de memória

```text
inicio {
    seja idade = 0
    escreva("Qual é a sua idade?")
    leia(idade)
    se idade >= 18 {
        escreva("Maior de idade")
    } senao {
        escreva("Menor de idade")
    }
}
```

`leia` recebe **uma variável inteira já declarada**, lê stdin nativamente e aceita sinal opcional, espaços, LF/CRLF e EOF após dígitos. Entradas vazias, letras, decimais e valores fora do intervalo de inteiros com sinal de 64 bits causam erro (código 1). O programa gerado não usa Python, mas a leitura inicial ainda é byte a byte e não está otimizada.

**Primeira otimização:** carga de constantes com instruções `mov` de 5 ou 7 bytes quando possível (em vez de sempre 10 bytes), sem alterar resultados ou flags. Cálculo dos endereços locais na pilha centralizado. Veja [arquitetura, ponteiros, memória e otimizações](docs/ARQUITETURA_E_OTIMIZACOES.md). Ponteiros brutos e heap ainda não estão implementados.

## Comece aqui no Windows

1. Baixe ou clone este repositório.
2. Instale Python 3 e confirme que `py -3 --version` funciona no PowerShell.
3. Dê dois cliques em **`INICIAR_RS.bat`**. O menu permanece disponível para você escolher as próximas operações.
4. Escolha **1** para compilar e executar `exemplos/tipos.rts`, **2** para editar no Bloco de Notas, **3** para executar os testes ou **4** para executar o último programa compilado.
5. Escolha **0** para sair.

**Importante:** `TESTAR_WINDOWS.bat` apenas executa um programa já compilado. Quando aparecer "pressione qualquer tecla", apertar uma tecla **encerra a janela**, não inicia uma nova etapa. Use `INICIAR_RS.bat` para trabalhar com o projeto.

### Novo na RS 0.4: repetição em português

O laço `enquanto` repete um bloco enquanto a condição for diferente de zero. `pare` interrompe o laço mais interno e `continue` passa para a próxima iteração do laço mais interno.

Arquivo `exemplos/tipos.rts`: 

```text
inicio {
    seja contador = 0
    enquanto contador < 5 {
        contador = contador + 1
        se contador == 3 {
            continue
        }
        escreva(contador)
        se contador == 4 {
            pare
        }
    }
}
```

Saída esperada: `1`, `2` e `4`, cada número em uma linha.

Laços podem ser aninhados e conter decisões `se`/`senao`. `pare` e `continue` fora de um laço produzem erro de compilação. Por enquanto, todas as variáveis devem ser declaradas fora dos blocos `se` e `enquanto`. Um laço sem condição de saída pode executar indefinidamente.

### Compilação manual

Windows, no PowerShell aberto na pasta do projeto:

```powershell
py -3 compilar.py exemplos\tipos.rts --alvo windows -o roteiro_windows.exe
.\roteiro_windows.exe
```

Linux x86-64:

```bash
python3 compilar.py exemplos/tipos.rts --alvo linux -o roteiro_linux
./roteiro_linux
```

Para rodar os testes automatizados:

```bash
python3 -m unittest discover -s testes -v
```

## Recursos implementados

- Programa `inicio { ... }`, instruções uma por linha e comentários `//`.
- `escreva("texto")` em UTF-8 e `escreva(expressão numérica)`.
- Variáveis `seja nome = expressão` e atribuição posterior `nome = expressão`.
- Inteiros de 64 bits com sinal; expressões `+`, `-`, `*`, `/`, `%` e parênteses.
- Biblioteca `inclua matematica`: `somar`, `subtrair`, `multiplicar`, `dividir`, `resto`.
- Comparações `==`, `!=`, `<`, `<=`, `>` e `>=`, que retornam 1 (verdadeiro) ou 0 (falso).
- `se condição { ... } senao { ... }`, incluindo blocos aninhados. `senao` é opcional.
- **Novo na 0.4:** `enquanto`, `pare` e `continue`, com laços aninhados e emissão direta de saltos x86-64.
- **Novo na 0.5:** `para nome de inicio ate fim [passo inteiro]`, inclusive e compilado diretamente em saltos nativos.
- Erros em português; divisão por zero e divisão inteira fora do intervalo retornam código de erro 1.

## Limitações conhecidas

- **Não há números decimais, entrada de texto**, funções criadas pelo usuário, aplicativos gráficos, jogos ou integração com bibliotecas externas.
- Por enquanto, variáveis precisam ser declaradas fora dos blocos `se`/`senao` e antes de serem utilizadas.
- Soma, subtração e multiplicação usam resultados de 64 bits sem detecção de estouro.
- Divisão inteira trunca em direção a zero (por exemplo, `-17 / 5` resulta em `-3`).
- O executável Windows gerado não foi executado por este ambiente Linux; a execução deve ser validada num Windows real. A estrutura PE é verificada nos testes.
- O formato PE atual usa três seções limitadas a 4 KiB cada. O compilador ainda não é endurecido para produção.
- A biblioteca matemática mapeia operações para instruções nativas; não é uma biblioteca Python instalada nos executáveis.

## Organização do código

- `sintaxe.py`: análise léxica, expressões e instruções.
- `codigo_nativo.py`: emissão de instruções AMD64 e formatos PE/ELF.
- `bibliotecas/matematica.py`: nomes públicos das funções matemáticas.
- `compilar.py`: interface de linha de comando.
- `testes/`: verificações automatizadas, incluindo execução nativa no Linux e no Windows quando disponíveis.
- `exemplos/`: programas `.rts` de referência.

**Próximas etapas:** tipos, referências seguras, entrada em blocos, números decimais, IR e benchmarks. Ainda não foi escolhida uma licença.
