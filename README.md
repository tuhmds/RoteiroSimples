# RoteiroSimples (RS) — versão experimental 0.2

Uma linguagem de programação **em português brasileiro**, com sintaxe simples e geração **direta de código de máquina x86-64**. Projeto experimental; ainda não é apropriado para sistemas em produção.

## Primeiro programa com matemática

Arquivo `exemplos/matematica.rts`:

```text
inclua matematica
início {
    seja preço = 10
    seja distancia = 5
    seja taxa = multiplicar(distancia, 2)
    escreva("Cálculo de entrega em reais inteiros:")
    escreva(somar(preço, taxa))
    escreva((10 + 5) * 2)
    escreva(dividir(-17, 5))
    escreva(resto(-17, 5))
}
```

Saída esperada:

```text
Cálculo de entrega em reais inteiros:
20
30
-3
-2
```

## Uso

O compilador de desenvolvimento está escrito em **Python 3.10 ou superior**; os executáveis gerados **não usam Python**, C, Rust, LLVM nem montador externo.

No Windows: execute `COMPILAR_WINDOWS.bat` (Python 3 instalado), ou rode:

```powershell
py -3 compilar.py exemplos\matematica.rts --alvo windows -o roteiro_windows.exe
.\roteiro_windows.exe
```

No Linux x86-64:

```bash
python3 compilar.py exemplos/matematica.rts --alvo linux -o roteiro_linux
./roteiro_linux
```

Para rodar os testes:

```bash
python3 -m unittest discover -s testes -v
```

## O que funciona

- `início { ... }`, uma instrução por linha, `//` para comentários;
- `escreva("texto")`, UTF-8, e `escreva(expressão numérica)`;
- variáveis `seja nome = expressão` e atribuição `nome = expressão`;
- números inteiros com sinal de 64 bits, incluindo negativos;
- `+`, `-`, `*`, `/`, `%`, parênteses e precedência matemática;
- `inclua matematica` com `somar`, `subtrair`, `multiplicar`, `dividir` e `resto`;
- divisão entre inteiros com truncamento em direção a zero (por exemplo, -17 / 5 = -3);
- erro de execução em português e saída com código 1 para divisão por zero e transbordamento específico `-2^63 / -1`;
- compilação nativa ELF64 Linux e PE32+ Windows (x86-64).

## Limitações e segurança

- **Ainda não há decimais**, condições, laços, funções criadas pelo usuário, interfaces ou suporte a jogos;
- a soma, subtração e multiplicação usam aritmética de 64 bits sem detecção de estouro (resultado modular);
- o executável Windows **não foi executado nesta sessão**: possui validação estática de estrutura PE; o teste de execução real deve rodar num Windows;
- o formato PE 0.2 é experimental e usa três seções limitadas a 4 KiB cada;
- ainda não há assinatura de executáveis, PIE/ASLR ou proteção de compilador de produção;
- cada comando ocupa uma linha; `inclua matematica` fica antes de `início`;
- a biblioteca matemática contém **mapeamentos de operações para instruções nativas**, não uma biblioteca de execução em Python.

O código da implementação está em `sintaxe.py` (análise), `codigo_nativo.py` (geração direta de bytes AMD64), `bibliotecas/matematica.py` (nomes de operações) e `compilar.py` (linha de comando).

**Próximas etapas:** decimais e regras de precisão, comparação, `se`/`senão`, laços, tipos, bibliotecas e testes contínuos em Windows e Linux. Licença e governança ainda não escolhidas.
