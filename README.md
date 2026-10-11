# RoteiroSimples (RS) — Protótipo 0.1

**Objetivo:** construir uma linguagem de programação de propósito geral, simples de aprender, cuja sintaxe, mensagens de erro e documentação sejam concebidas em português brasileiro.

Este pacote é **o primeiro experimento funcional**, não a linguagem completa. Ele recebe um arquivo `.rts` e produz **código de máquina x86-64 diretamente**, em um executável Windows (`.exe`, formato PE32+) ou Linux (formato ELF64). O compilador experimental foi escrito em Python 3 para acelerar a primeira etapa; os executáveis produzidos **não dependem de Python** e não passam por compiladores C, Rust ou montadores Assembly.

## Teste imediato no Windows (sem instalar Python)

1. Extraia o ZIP para uma pasta.
2. Dê dois cliques em **`TESTAR_WINDOWS.bat`**. Ele abre o `.exe` já gerado e deixa a janela aberta para você conferir a saída.
3. A saída esperada é:

    Olá, mundo!
    O RoteiroSimples está funcionando!

**Teste real em Windows:** a versão anterior deste mesmo gerador, com a mesma geração de código, foi executada com sucesso pelo usuário no Windows em 11/10/2026. O pacote renomeado preserva o funcionamento do gerador; o executável atualizado deve ser testado novamente no seu computador.

## Escrever e compilar seus próprios programas no Windows

1. Instale Python 3 caso ainda não tenha. Python é necessário **para executar o compilador experimental**, não para executar o `.exe` criado.
2. Abra `exemplos/ola.rts` no Bloco de Notas e mude a mensagem entre aspas.
3. Dê dois cliques em **`COMPILAR_WINDOWS.bat`**, que recompila `exemplos/ola.rts` e executa a nova versão.

Ou, no PowerShell aberto na pasta extraída:

```powershell
py -3 compilar.py exemplos\ola.rts --alvo windows -o meu_programa.exe
.\meu_programa.exe
```

## Exemplo de código

```text
início {
    escreva("Olá, mundo!")
    escreva("O RoteiroSimples está funcionando!")
}
```

### Regras que já funcionam

- O programa começa com `início {` e termina com `}` em linhas próprias.
- Cada instrução `escreva("mensagem")` imprime um texto e acrescenta uma quebra de linha.
- Caracteres acentuados são aceitos em UTF-8.
- `\n` dentro da mensagem significa quebra de linha.
- Linhas inteiras iniciadas com `//` são comentários.
- A instrução `escreva` aceita ou não `;` no fim.
- Erros de escrita dessa pequena sintaxe já são comunicados em português.

### O que ainda NÃO funciona

Variáveis (`seja`), contas, condições (`se`/`senão`), laços, funções, tipos, bibliotecas, interfaces, jogos, depuração e otimização. Esse código é um **primeiro compilador experimental de textos**, e não um compilador de uso geral. O alvo Windows utiliza a API do sistema `WriteFile` para saída, com página de código UTF-8; seu funcionamento real em consoles diferentes ainda precisa ser testado. Não existe assinatura digital, ASLR ou infraestrutura de segurança de compilador de produção nesta versão.

## Linux x86-64

```bash
python3 compilar.py exemplos/ola.rts --alvo linux -o meu_programa
./meu_programa
```

O executável Linux foi de fato executado e imprimiu os textos esperados neste ambiente.

## Testes automatizados

```bash
python3 -m unittest discover -s testes -v
```

Testam análise do código, erros simples, UTF-8 e execução nativa no Linux; a saída do compilador Windows tem verificação estática de estrutura PE e importações (não é um teste em execução Windows).

## Como ele funciona por dentro

1. Lê o código em português do arquivo `.rts`.
2. Identifica as instruções atualmente aceitas e valida a escrita.
3. Constrói os bytes de instruções x86-64 e guarda as mensagens.
4. Ajusta os deslocamentos dos endereços usados pelas instruções.
5. Grava os cabeçalhos e as seções do arquivo ELF64 ou PE32+, com as chamadas necessárias ao sistema operacional.

## Próxima versão sugerida: 0.2

Substituir a leitura simples de linhas por um analisador léxico e sintático de verdade. Em seguida, implementar variáveis e expressões (`seja preço = 10`, `escreva(preço + 2)`), com testes nos dois sistemas. Depois virão decisões, repetições e funções. Não vamos anunciar suporte a jogos ou aplicativos até haver compilador, biblioteca e ferramentas adequados.

**Nome oficial:** RoteiroSimples (RS). A extensão `.rts` evita conflito com a extensão `.rs` do Rust. A licença e o modelo de governança ainda não foram definidos.

## Mudanças de identidade neste pacote

Nome oficial **RoteiroSimples (RS)**, extensão `.rts`, mensagens dos scripts `.bat` e nomes dos executáveis atualizados. A lógica de geração de código de máquina foi preservada. A versão 0.1 continua limitada ao comando `escreva`.
