# Sistema de módulos — RoteiroSimples RS 0.27

A RS 0.27 permite distribuir tipos e funções em diversos arquivos `.rts` e reuni-los em **um único executável nativo**. Os módulos são resolvidos na compilação; o executável não carrega arquivos `.rts` ao iniciar.

## Sintaxe

No programa principal:

```text
importe "modulos/pedidos.rts"
inicio {
    seja pedido: Pedido
    pedido.preco = 25
    pedido.quantidade = 4
    escreva(calcular_pedido(pedido))
}
```

No módulo `modulos/pedidos.rts`:

```text
importe "valores.rts"
tipo Pedido {
    preco: inteiro
    quantidade: inteiro
}
funcao calcular_pedido(pedido: Pedido) -> inteiro {
    retorne acrescentar_taxa(pedido.preco * pedido.quantidade)
}
```

O módulo `modulos/valores.rts` define a função `acrescentar_taxa`.

## Compilação

Windows:

```powershell
py -3 compilar.py exemplos\projeto_modulos.rts --alvo windows -O 8 --mostrar-modulos -o roteiro_windows.exe
.\roteiro_windows.exe
```

Linux:

```bash
python3 compilar.py exemplos/projeto_modulos.rts --alvo linux -O 8 --mostrar-modulos -o roteiro_linux
./roteiro_linux
```

## Regras e segurança

- O programa principal contém exatamente um `inicio`. Um módulo importado pode definir `tipo` e `funcao` e importar outros módulos, mas não pode conter `inicio`.
- A importação usa um caminho relativo ao arquivo importador. Use `/` como separador, também no Windows, e a extensão `.rts`.
- Arquivos importados precisam permanecer dentro da pasta do projeto (pasta do arquivo principal). Caminhos absolutos, trajetos que saem da pasta e ligações simbólicas apontando para fora são rejeitados.
- Um módulo importado por diversos caminhos é incluído uma única vez. Dependências circulares geram um erro com a sequência de arquivos.
- A resolução é determinística: primeiro as dependências, depois os arquivos importadores. Tipos são reunidos antes das funções; campos que utilizam tipos próprios dependem de definições previamente conhecidas.
- **Há um espaço global único de tipos e funções nesta versão.** Não existem nomes qualificados, visibilidade privada nem apelidos de importação. Nomes duplicados são erros.
- `inclua matematica` pode estar em um módulo e valerá para o programa reunido.
- O compilador converte mensagens que trazem números de linha para o arquivo original quando há importações.
- `--mostrar-modulos` mostra a ordem de arquivos usados na compilação.

## Compatibilidade e limitações

Os programas sem importações continuam sendo analisados a partir do **texto original, sem alterações**, preservando inclusive os números de linha. Os níveis `-O 0` a `-O 8` permanecem disponíveis; não foi criado outro nível.

Esta primeira etapa faz a reunião dos arquivos antes da análise sintática. Não há variáveis globais de módulo, inicialização própria, compilação incremental, módulos binários ou tratamento de nomes privados. A RS continua experimental; não utilizar em produção.

Nomenclatura nova em português brasileiro. Comandos e identificadores não levam acentos; mensagens e documentação podem usar acentuação normal.
