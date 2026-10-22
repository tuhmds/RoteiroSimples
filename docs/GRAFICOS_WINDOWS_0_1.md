# RS Gráficos 0.1 — diálogo nativo Windows

**Estado: experimental, sujeito à validação no Windows.**

Este primeiro passo cria um diálogo de mensagem **modal** por meio da API
`MessageBoxW`, importada de `USER32.dll` em um executável PE32+ AMD64.
O código-fonte é escrito em RoteiroSimples e compilado pelo compilador de
desenvolvimento existente. O executável não depende de Python.

## Uso

```rts
inicio {
    janela_mensagem("RoteiroSimples", "Ola, mundo grafico! 🌱")
}
```

Compilação no Windows, a partir da raiz do repositório:

```powershell
python compilar.py exemplos/graficos/janela_mensagem_windows.rts --alvo windows -O 0 -o primeira_janela.exe
.\primeira_janela.exe
```

O diálogo bloqueia a execução até o botão OK ser pressionado. O programa
continua usando o subsistema **console** do PE: há uma janela de console e
outra, modal, do Windows. **Ainda não há janela própria persistente, desenho,
eventos, botões personalizados, editor ou game loop.**

## Contrato da operação

`janela_mensagem("Titulo", "Mensagem")` recebe **dois literais**
entre aspas duplas. O título precisa ser não vazio. Cada literal tem
até 4096 unidades UTF-16; NUL, UTF-16 inválido e valores não literais são
rejeitados na compilação. Pode ser usado em blocos e funções, com execução
sequencial. Não retorna qual botão foi pressionado. Só o alvo Windows
é aceito: o alvo Linux informa erro em vez de gerar um executável inválido.

Os textos são emitidos em `.rdata` como UTF-16LE terminados em NUL.
O gerador mantém a ABI AMD64 Windows: RCX = HWND nulo, RDX = texto,
R8 = título, R9D = `MB_OK`; a chamada indireta resolve o IAT
`USER32!MessageBoxW`. O PE histórico mantém `KERNEL32.dll`;
apenas os programas que usam a operação ganham um segundo descritor de DLL.
Não se adicionam bibliotecas Python de interface, C, LLVM ou SDL à execução.

## Verificações

```shell
python -m unittest testes.test_graficos_windows_rs -v
python -m unittest discover -s testes -v
```

Os testes conferem a análise sintática, decisões da IR, múltiplos literais,
UTF-16LE, dois descritores de importação PE, alvos e diagnósticos. Eles
**não** comprovam a aparição visual do diálogo. Para homologar a GUI é
necessário rodar o exemplo em Windows com sessão de desktop interativa e
inspecionar a exibição, clique no botão e retorno à execução.

## Próximos passos

1. Validar execução visual real e registrar resultados por versão do Windows.
2. Separar o subsistema GUI do console com critério explícito por programa.
3. Expor janela própria e ciclo de eventos com `CreateWindowExW`.
4. Construir gráficos 2D e entradas de mouse/teclado, antes de avançar a GPU.

Este módulo não participa da representação intermediária otimizada.
A estratégia é conservadora para programas que usam `janela_mensagem`.
