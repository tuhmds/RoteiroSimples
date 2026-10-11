# RoteiroSimples (RS) — versão experimental 0.4

**RoteiroSimples** é um projeto experimental de linguagem de programação em português brasileiro. O compilador de desenvolvimento está escrito em Python 3.10+ e gera instruções x86-64 diretamente para executáveis Windows (PE32+) e Linux (ELF64), sem passar por C, Rust ou LLVM. Os programas gerados não precisam de Python para executar.

> Estado do projeto: protótipo educacional. Ainda não é seguro para sistemas de produção.

## Comece aqui no Windows

1. Baixe ou clone este repositório.
2. Instale Python 3 e confirme que `py -3 --version` funciona no PowerShell.
3. Dê dois cliques em **`INICIAR_RS.bat`**. O menu permanece disponível para você escolher as próximas operações.
4. Escolha **1** para compilar e executar `exemplos/repeticao.rts`, **2** para editar no Bloco de Notas, **3** para executar os testes ou **4** para executar o último programa compilado.
5. Escolha **0** para sair.

**Importante:** `TESTAR_WINDOWS.bat` apenas executa um programa já compilado. Quando aparecer "pressione qualquer tecla", apertar uma tecla **encerra a janela**, não inicia uma nova etapa. Use `INICIAR_RS.bat` para trabalhar com o projeto.

### Novo na RS 0.4: repetição em português

O laço `enquanto` repete um bloco enquanto a condição for diferente de zero. `pare` interrompe o laço mais interno e `continue` passa para a próxima iteração do laço mais interno.

Arquivo `exemplos/repeticao.rts`: 

```text
início {
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

Laços podem ser aninhados e conter decisões `se`/`senão`. `pare` e `continue` fora de um laço produzem erro de compilação. Por enquanto, todas as variáveis devem ser declaradas fora dos blocos `se` e `enquanto`. Um laço sem condição de saída pode executar indefinidamente.

### Compilação manual

Windows, no PowerShell aberto na pasta do projeto:

```powershell
py -3 compilar.py exemplos\repeticao.rts --alvo windows -o roteiro_windows.exe
.\roteiro_windows.exe
```

Linux x86-64:

```bash
python3 compilar.py exemplos/repeticao.rts --alvo linux -o roteiro_linux
./roteiro_linux
```

Para rodar os testes automatizados:

```bash
python3 -m unittest discover -s testes -v
```

## Recursos implementados

- Programa `início { ... }`, instruções uma por linha e comentários `//`.
- `escreva("texto")` em UTF-8 e `escreva(expressão numérica)`.
- Variáveis `seja nome = expressão` e atribuição posterior `nome = expressão`.
- Inteiros de 64 bits com sinal; expressões `+`, `-`, `*`, `/`, `%` e parênteses.
- Biblioteca `inclua matematica`: `somar`, `subtrair`, `multiplicar`, `dividir`, `resto`.
- Comparações `==`, `!=`, `<`, `<=`, `>` e `>=`, que retornam 1 (verdadeiro) ou 0 (falso).
- `se condição { ... } senão { ... }`, incluindo blocos aninhados. `senão` é opcional.
- **Novo na 0.4:** `enquanto`, `pare` e `continue`, com laços aninhados e emissão direta de saltos x86-64.
- Erros em português; divisão por zero e divisão inteira fora do intervalo retornam código de erro 1.

## Limitações conhecidas

- **Não há números decimais**, `para`, funções criadas pelo usuário, aplicativos gráficos, jogos ou integração com bibliotecas externas.
- Por enquanto, variáveis precisam ser declaradas fora dos blocos `se`/`senão` e antes de serem utilizadas.
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

**Próximas etapas:** implementar `para`, entrada de dados e tipos, adicionar decimais com regras explícitas de precisão, ampliar a biblioteca padrão e as verificações automatizadas. Ainda não foi escolhida uma licença.
