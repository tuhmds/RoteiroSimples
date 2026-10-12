# RoteiroSimples (RS) — versão experimental 0.23

Linguagem experimental em português brasileiro, com compilador em Python 3.10+ que **gera diretamente instruções de máquina x86-64**, em executáveis ELF64 (Linux) e PE32+ (Windows). Os programas gerados não dependem do Python para executar. **Não usar em produção.**

## Novo na RS 0.23 — fundação: escopos, funções e dimensionamento

A RS continua com **comandos e identificadores sem acentos**, e mensagens,
nomes públicos e terminologia técnica em **português brasileiro**. A prioridade
desta versão é a estrutura da linguagem, não outro nível de otimização.

```text
funcao calcular_total(preco: inteiro, quantidade: inteiro) -> inteiro {
    seja total = preco * quantidade
    retorne total
}

inicio {
    seja preco = 25
    escreva(calcular_total(preco, 4))
}
```

O programa imprime **100**, executando chamada e retorno reais em x86-64.

**Implementado:**

- Escopos léxicos para `se`, `senao`, `enquanto` e `para`, com sombreamento e
  proibição de acesso a nomes locais depois que o bloco termina.
- Funções antes do bloco `inicio`, com parâmetros `inteiro`/`logico`, tipo de
  retorno explícito, `retorne`, chamadas encadeadas e quadros independentes
  na pilha, usando convenção interna do compilador.
- Verificação de quantidade e tipos de argumentos, retorno obrigatório em
  todos os caminhos e diagnóstico de recursão direta ou indireta.
- Memória local calculada por tamanho: foram removidos o teto de 256 slots,
  a capacidade máxima arbitrária de listas e textos e o teto de 4 KiB das
  seções Windows. O compilador respeita o limite real do endereçamento
  relativo do gerador; usa sondagem de páginas para quadros grandes, e laços
  de inicialização para listas/buffers de maior capacidade.
- Compatibilidade com programas das versões anteriores e manutenção das
  opções `-O 0` a `-O 8`. Nos programas que usam funções ou escopos locais,
  a geração nativa é conservadora; as otimizações SSA desses casos ainda
  precisam ser adaptadas aos novos escopos e quadros de chamada.

**Ainda não implementado:** recursão segura, parâmetros e retornos compostos
(textos/listas), entrada de dados dentro de funções, tipos criados pelo
programador, memória dinâmica e verificação estática de tempo de vida.
A política de escopo do contador `para` permanece compatível: um contador
novo pertence ao bloco que contém o laço e continua acessível após ele.
O limite prático de pilha depende do sistema operacional e do executável;
não se promete alocação infinita nem segurança completa de memória.

Veja [Fundamentos da RS 0.23](docs/FUNDACAO_RS_0_23.md) e
`exemplos/funcoes_escopos.rts`.

---

## Novo na RS 0.22 — propagação de valores entre blocos

A linguagem mantém palavras reservadas **sem acentos**. As mensagens, a documentação e a terminologia técnica usam **português brasileiro**: grafo de fluxo de controle, memória versionada, nós de junção, propagação de valores e gerador nativo. Nomes anteriores usados por ferramentas continuam disponíveis como alternativas de compatibilidade.

O novo nível **`-O 8`** propaga valores conhecidos de posições de listas entre os blocos do programa. Um valor só é usado depois de uma decisão se **todos os caminhos possíveis concordarem**. A análise também examina laços e descarta o conhecimento quando há escrita capaz de alterar aquela posição.

Exemplo: se ambos os ramos de `se` atribuírem `42` a `notas[0]`, uma leitura posterior pode ser substituída por `42`. Caso haja valores diferentes, leitura pelo teclado, índice variável ou risco de erro, as verificações necessárias continuam ativas.

- **Implementado:** propagação de valores de listas locais em junções e laços; remoção de escritas literais comprovadamente redundantes; preservação do comportamento de `-O 0` a `-O 7`.
- **Ainda pendente:** referências, ponteiros brutos, alocação dinâmica e otimizações gerais de memória com nomes compartilhados.

Consulte [Propagação entre blocos — RS 0.22](docs/PROPAGACAO_ENTRE_BLOCOS_RS_0_22.md) para a especificação, os limites e o vocabulário adotado.

```powershell
py -3 compilar.py exemplos\memoria_entre_blocos.rts --alvo windows -O 8 --mostrar-ir --mostrar-memoria-versionada -o roteiro_windows.exe
.\roteiro_windows.exe
```

---

## Novo na RS 0.21 — primeira otimizacao real guiada pela Memory SSA

O novo nível **`-O 7`** usa as versões de memória da RS 0.20 para otimizar
acessos a **listas locais de inteiros com índice literal comprovadamente válido**:

- **Encaminhamento de valores:** `a[0] = 10; escreva(a[0])` vira uma leitura
  direta da constante `10` no código nativo. Elementos nunca escritos começam
  com `0`, conforme a regra de inicialização de listas.
- **Escritas redundantes:** `a[0] = 10; a[0] = 10` mantém apenas uma escrita.
- **Dependências verificadas:** a substituição exige a versão correta da
  região na Memory SSA. Uma escrita com índice dinâmico, `leia(a[i])`, decisão
  ou laço invalida o conhecimento conservador conforme necessário.
- **Erros preservados:** índices inválidos continuam falhando. Divisões por
  zero e operações que podem sofrer estouro **nunca são eliminadas** por essa
  otimização. Textos, I/O e efeitos de outras regiões não são reordenados.

As transformações **não** implementam aliasing, referências, otimização global
por blocos nem o backend SSA com listas. A geração nativa das listas continua
com as verificações de capacidade e de índice da RS 0.17. Os níveis anteriores
`-O 0..6` permanecem inalterados.

Exemplo:

```text
inicio {
    seja valores: lista[4]
    valores[0] = 10
    valores[1] = 20
    valores[1] = 20
    escreva(valores[0] + valores[1])
}
```

Para experimentar no Windows:

```powershell
py -3 compilar.py exemplos\memoria_otimizada.rts --alvo windows -O 7 --mostrar-ir -o roteiro_windows.exe
.\roteiro_windows.exe
```

Veja [otimização segura de memória RS 0.21](docs/OTIMIZACAO_MEMORIA_RS_0_21.md).

## Novo na RS 0.20 — Memory SSA por objeto e efeito

A RS agora **versiona leituras e escritas em memória** sobre o CFG. Cada lista ou
buffer local possui sua própria cadeia de versões, enquanto `leia`, `escreva`
e possíveis erros usam cadeias de dependência de efeito observável. Junções
de caminhos e laços criam nós `phi` de memória. O verificador confere
unicidade, dominância, preenchimento de `phi` e ordem das escritas.

```powershell
py -3 compilar.py exemplos\memory_ssa.rts --alvo windows -O 6 --mostrar-memory-ssa --salvar-memory-ssa memoria.json -o roteiro_windows.exe
.\roteiro_windows.exe
```

A opção **C** de `INICIAR_RS.bat` mostra as versões e salva `memoria.json`.
**Isso é análise, não uma otimização ativa do backend**: programas com listas e
textos ainda usam o caminho de pilha com verificações de limites, inclusive
com `-O 6`. A RS continua sem ponteiros, aliases, heap ou empréstimos; os
modelos de referência ainda precisam ser implementados. Leia a
[especificação da Memory SSA](docs/MEMORY_SSA_RS_0_20.md).

Exemplo: `exemplos/memory_ssa.rts` (saída `Olá.!.` e `20`).

## Novo na RS 0.19 — leitura bufferizada e efeitos de memória

- **I/O nativa em blocos:** `leia` agora usa um cache único de **1.024 bytes no Linux e 256 bytes no Windows**
  para inteiros, elementos de listas e textos UTF-8. Leituras consecutivas
  reaproveitam corretamente os bytes já recebidos por pipe ou console.
- **Proteções preservadas:** índices, capacidade dos buffers, UTF-8 e
  limites numéricos continuam verificados. A pilha mantém o orçamento
  provisório conservador até implementarmos sondagem de páginas Windows.
- **Efeitos da IR:** `compilador/efeitos.py` identifica leituras/escritas,
  entrada e saída e possíveis falhas, inclusive dentro de laços e decisões.
  Use `--mostrar-efeitos` e `--salvar-efeitos efeitos.json`.
- **Na RS 0.19 ainda não havia Memory SSA:** não aplicávamos movimentação/eliminações de
  operações de memória. Listas e textos continuam com backend de pilha em
  qualquer nível de otimização.
- **Compatibilidade:** programas antigos que não usam `leia` preservam seus
  executáveis; os que usam leitura ganham outra implementação nativa.

[Detalhes técnicos e medição](docs/ENTRADA_E_EFEITOS_RS_0_19.md).
Exemplo: `exemplos/entrada_bufferizada.rts`.

## Incluído na RS 0.18 — buffers UTF-8 com comprimento e capacidade

`texto[N]` reserva **N bytes** de dados na pilha e um comprimento de 64 bits. Sem ponteiros brutos, sem terminador NUL obrigatório e sem truncamento silencioso:

```text
inicio {
    seja nome: texto[48]
    seja outro: texto[32]
    copie(nome, "Olá, ")
    copie(outro, "mundo 🌎")
    junte(nome, outro)
    escreva(nome)
    escreva(tamanho(nome))
    escreva(capacidade(nome))
    limpe(outro)
    leia(outro)
    escreva(outro)
}
```

`copie` e `junte` aceitam literais ou outro buffer. `limpe` zera o comprimento lógico; `leia` lê uma linha do teclado e **verifica UTF-8 e capacidade**. `tamanho` retorna **bytes ocupados**, e `capacidade` retorna bytes reservados: `á` ocupa dois bytes, `🌎` ocupa quatro. Excesso de capacidade ou UTF-8 inválido provoca erro e saída `1`. Buffers não podem ser usados diretamente em contas ou como ponteiros.

A memória continua na pilha, com orçamento total conservador de 256 slots de 8 bytes (inclui listas, buffers e suas informações de comprimento); capacidades individuais vão de 1 a 2040 bytes, respeitando esse orçamento. Programas com buffers ou listas usam o backend seguro de pilha em qualquer nível `-O 0..6`; CFG/SSA escalar ainda não otimiza dados de memória estruturada. A análise Memory SSA foi adicionada na RS 0.20. Desde a RS 0.19, a entrada usa um cache compartilhado de 1.024 bytes no Linux e 256 bytes no Windows.

**Ainda não há** empréstimos/referências, ponteiros, heap, slices, strings dinâmicas ou garantia de que uma escrita parcial de sistema seja refeita. As regras de propriedade, empréstimo compartilhado e mutável, aliasing e tempo de vida são apenas uma especificação futura. Consulte [buffers e plano de referências](docs/MEMORIA_TEXTO_RS_0_18.md).

## Incluído na RS 0.17 — listas de inteiros com memória verificada

As listas de tamanho fixo ocupam uma região contígua da **pilha** do programa, com
8 bytes por elemento. Todo elemento é inicializado em zero. Os índices começam
em `0` e são verificados **antes de cada leitura ou escrita**, inclusive se o
índice for calculado em tempo de execução. Acesso inválido encerra o executável
com código 1 e mensagem de erro; nunca permite escrever fora da lista.

```text
inicio {
    seja numeros: lista[5]
    seja soma = 0
    para i de 0 ate tamanho(numeros) - 1 {
        numeros[i] = (i + 1) * 10
        soma = soma + numeros[i]
    }
    escreva("Soma da lista:")
    escreva(soma)
}
```

Saída esperada: `Soma da lista:` e `150`. Também é possível usar
`leia(numeros[1])` para inserir um inteiro pelo teclado.

- São aceitas apenas listas de **`inteiro`**, com comprimento constante de 1 a 256.
- O limite provisório soma todos os elementos e variáveis locais: **256 posições
  de 8 bytes**, ou até 2 KiB de dados locais (fora das rotinas auxiliares).
- `tamanho(numeros)` retorna o comprimento definido na declaração (sem acessar memória).
- Listas inteiras não podem ser atribuídas, copiadas ou passadas como valores.
- A implementação inicial utiliza o backend de pilha com checagem em todos os níveis
  `-O 0` a `-O 6`. **As otimizações SSA de registradores não são aplicadas aos
  programas que contêm listas**, até haver uma modelagem explícita dos efeitos
  de memória na IR e SSA. Programas sem listas preservam o backend SSA.
- Na RS 0.17 ainda não existiam heap, ponteiros, referências, buffers de texto ou listas
  dinâmicas. Essas funcionalidades precisarão de regras explícitas de propriedade,
  tempo de vida, aliasing e limites antes de serem implementadas.

**Exemplo:** `exemplos/listas.rts`. No Windows:

```powershell
py -3 compilar.py exemplos\listas.rts --alvo windows -O 6 -o roteiro_windows.exe
.\roteiro_windows.exe
```

Consulte [memória e listas na RS 0.17](docs/MEMORIA_LISTAS_RS_0_17.md).

## Incluído desde a RS 0.16 — coalescência e saltos curtos (`-O 6`)

O nível **`-O 6`** conserva a SSA nativa e o layout do `-O 5`, acrescentando três otimizações:

- **Coalescência conservadora:** versões SSA ligadas por nós `phi` preferem uma mesma localização física se **não houver interferência**. A vivacidade continua determinando se o compartilhamento é permitido; não removemos verificações de overflow.
- **Cópias diretas:** quando ainda é necessária uma cópia entre dois registradores, o backend emite `mov destino, origem` sem transferir duas vezes por `rax`. Cópias paralelas cíclicas ainda usam um slot temporário.
- **Relaxação de saltos:** após emitir o executável, saltos SSA locais que cabem em `rel8` (deslocamento de -128 a 127 bytes) são encurtados de 5/6 para 2 bytes. O compilador recalcula todas as posições de rótulos e referências `rel32` de chamadas e dados, antes de montar PE32+ ou ELF64. Saltos que não cabem permanecem longos.

Os níveis **`-O 0` a `-O 5` continuam sem mudanças**. Esta otimização é experimental; preservamos um conjunto de testes comparando saída, código de retorno, erros aritméticos, laços e leitura pelo teclado entre `-O 5` e `-O 6` em Windows e Linux.

```powershell
py -3 compilar.py exemplos\registradores.rts --alvo windows -O 6 --mostrar-alocacao -o roteiro_windows.exe
.\roteiro_windows.exe
```

Para medir desempenho e tamanho, execute `py -3 benchmarks\medir.py --repeticoes 9 --json resultados.json` no Windows, ou o equivalente com `python3` no Linux. O resultado depende de máquina, carga e cache e **não garante aceleração em todos os programas**. Veja [documentação do backend](docs/OTIMIZACAO_RS_0_16.md).

## Incluído desde a RS 0.15 — layout de blocos e benchmark nativo

A opção `-O 5` usa a mesma SSA e alocação de registradores da RS 0.14, mas **reordena blocos básicos**, permite queda natural entre blocos adjacentes e reduz saltos incondicionais. Quando um bloco tem ramificações, a emissão preserva cópias `phi` em cada aresta; desvios que precisam de cópias usam trampolins próprios. Todos os níveis `-O 0..4` continuam disponíveis.

```powershell
py -3 compilar.py exemplos\layout.rts --alvo windows -O 5 -o roteiro_windows.exe
.\roteiro_windows.exe
py -3 benchmarks\medir.py --repeticoes 7 --json resultados.json
```

Os benchmarks medem tempos de execução real por mediana, excluem compilação e conferem que saída e código de retorno são idênticos. Resultados dependem de CPU, sistema e carga; [veja o protocolo](docs/LAYOUT_RS_0_15.md). **Não confundir redução do tamanho dos executáveis com aumento garantido de velocidade.**

## Novo na RS 0.14 — SSA executável e primeira alocação de registradores

O nível experimental **`-O 4`** constrói a SSA sobre o CFG, aloca localizações físicas para cada versão e gera o próprio fluxo de controle com instruções nativas x86-64. Os nós `phi` deixam de ser somente uma análise: viram **cópias executáveis em cada aresta**, inclusive nas arestas de decisão e nos laços. Cópias paralelas com ciclos são resolvidas usando um espaço temporário reservado, sem destruir valores.

- **Alocação por interferência/vivacidade:** as versões SSA mais usadas podem ficar em `r13`, `r14` e `r15`, preservados durante as rotinas de entrada/saída. As demais utilizam posições reutilizáveis na pilha, com limite conservador de 256 slots (incluindo um temporário adicional).
- **Fluxo sem riscos aritméticos silenciosos:** `+`, `-`, `*`, `/`, `%` e negação preservam os testes de erro das versões anteriores. Em `para`, quando o incremento estoura, o contador mantém o valor anterior e o laço termina, preservando o comportamento já definido.
- **Compatibilidade:** os níveis `-O 0` a `-O 3` continuam usando o backend legado. A nova opção é experimental e deve ser comparada com `-O 3` antes de uso intensivo.
- **Tamanho e desempenho:** os exemplos medidos em Linux ficaram maiores no novo nível por conta de saltos adicionais entre blocos, embora o código agora use registradores para valores SSA. Não há promessa de ganho de velocidade. Melhorar disposição dos blocos e reduzir saltos será a próxima frente.
- **Sem ponteiros, heap ou otimizações inseguras:** continua sendo um protótipo educacional.

**Exemplo:** `exemplos/registradores.rts`. Windows:

```powershell
py -3 compilar.py exemplos\registradores.rts --alvo windows -O 4 --mostrar-alocacao --mostrar-copias-phi -o roteiro_windows.exe
.\roteiro_windows.exe
```

Linux:

```bash
python3 compilar.py exemplos/registradores.rts --alvo linux -O 4 --mostrar-alocacao -o roteiro_linux
./roteiro_linux
```

Confira a documentação [SSA e registradores RS 0.14](docs/SSA_BACKEND_RS_0_14.md).

## RS 0.13 — SSA agora otimiza código nativo com `-O 3`

**Novidade funcional:** a RS utiliza versões SSA para propagar constantes entre blocos de controle, inclusive através de nós `phi` quando os valores de todos os predecessores concordam. A IR reescrita é passada ao mesmo backend x86-64 das versões anteriores. Este é o **primeiro uso da SSA na geração dos executáveis**, não uma substituição completa do backend pela SSA.

- **`-O 3`:** herda `-O 2` e habilita propagação conservadora entre blocos com versões SSA e nós `phi`.
- **Remoção segura de atribuições mortas:** uma atribuição só é retirada quando o resultado é um literal sem efeitos e não haverá leitura posterior da variável (análise de vivacidade). Operações que podem gerar estouro, divisão por zero ou erro de entrada permanecem.
- **Diagnóstico de cópias `phi`:** `--mostrar-copias-phi` lista por aresta os pares origem/destino das cópias paralelas. **Esse plano ainda não é emitido no código de máquina**; o backend continua utilizando slots de pilha. Tampouco há alocador de registradores nesta versão.
- **Compatibilidade:** `-O 0`, `-O 1`, `-O 2` preservam os 72 binários de referência; `-O 3` é experimental. O padrão ainda é `-O 1`.
- A fase não altera palavras-chave, tipos, ponteiros ou o modelo de memória da linguagem. Comandos e identificadores **não têm acentos**; textos são UTF-8.

Exemplo: `exemplos/ssa_otimizacao.rts`. Ambos os caminhos do `se` atribuem `42` à mesma variável. No encontro dos caminhos, o `phi` permite substituir `escreva(pontos)` por uma impressão da constante. A vivacidade permite remover as atribuições que ficaram sem leitores. O programa continua exibindo `42` com qualquer nível de otimização.

Windows:

```powershell
py -3 compilar.py exemplos\ssa_otimizacao.rts --alvo windows -O 3 --mostrar-ir --mostrar-copias-phi -o roteiro_windows.exe
.\roteiro_windows.exe
```

Linux:

```bash
python3 compilar.py exemplos/ssa_otimizacao.rts --alvo linux -O 3 -o roteiro_linux
./roteiro_linux
```

Veja [detalhes de otimização SSA da RS 0.13](docs/OTIMIZACAO_SSA_RS_0_13.md). Os próximos desafios são o **baixamento real dos `phi` em cópias paralelas** (com ciclos e arestas críticas), alocação de registradores e benchmarking de desempenho. Tamanho do arquivo não equivale necessariamente a velocidade.

## RS 0.12 — Conversão para SSA tipada (modo de análise)

A RS 0.12 introduz uma representação **SSA (Static Single Assignment)** construída sobre o CFG da RS 0.10 e sobre os dominadores e a vivacidade da RS 0.11. Cada definição recebe uma versão própria (`pontos@0`, `pontos@1`), e **nós `phi` completos** registram qual versão vem de cada predecessor, inclusive em retroarestas de `enquanto` e `para`.

**Importante:** a SSA é construída, renomeada e validada por dominância, mas ainda **não é usada pelo backend nativo**. `-O 0`, `-O 1` e `-O 2` continuam produzindo os mesmos executáveis da RS 0.11 para os programas existentes. Não alegamos aceleração nesta etapa.

### Experimente no Windows

```powershell
py -3 compilar.py exemplos\ssa.rts --alvo windows -O 2 --mostrar-ssa --salvar-ssa ssa.json -o roteiro_windows.exe
.\roteiro_windows.exe
```

O menu `INICIAR_RS.bat` agora inclui a **opção 7** para mostrar a SSA e salvar `ssa.json`. O arquivo JSON contém definições únicas, operadores e expressões renomeadas, `phi` por predecessor e as fronteiras de dominância. Os arquivos `.rts` continuam com comandos e identificadores **sem acentos**.

Consulte [a especificação de SSA](docs/SSA_RS_0_12.md). As próximas etapas serão baixar a SSA para código nativo, fazer eliminação de código morto segura e desenvolver alocação de registradores, com testes de equivalência.

## RS 0.11 — Fluxo de dados, vivacidade e otimização local O2

A RS 0.11 mantém os comandos **sem acentos** e preserva a compatibilidade com os programas anteriores. O novo módulo `compilador/fluxo_dados.py` analisa o CFG para calcular definições alcançantes, variáveis vivas e dominadores. Ele identifica **candidatos a junções `phi`**, mas **ainda não converte o programa para SSA real**.

Com `-O 2`, a IR aplica uma propagação **conservadora e local** de constantes em trechos sequenciais, sem mover ou remover operações, e invalida suposições ao encontrar decisões e laços. `-O 0` e `-O 1` preservam o comportamento da RS 0.10; `-O 1` continua sendo o padrão.

### Exemplo novo

```text
inicio {
    seja a = 2
    seja b = a * 3 + 4
    escreva(b) // 10
}
```

Inspecione as variáveis vivas e os pontos em que dois caminhos se encontram:

```powershell
py -3 compilar.py exemplos\fluxo_dados.rts --alvo windows -O 2 --mostrar-fluxo --salvar-fluxo analise.json --mostrar-ir -o roteiro_windows.exe
.\roteiro_windows.exe
```

- `--mostrar-fluxo`: relatório em texto por bloco do CFG.
- `--salvar-fluxo analise.json`: relatório estruturado em JSON UTF-8.
- `-O 2`: ativa a propagação local de valores constantes, sem perda das verificações de estouro ou divisão por zero.
- `INICIAR_RS.bat`: nova **opção 6** para executar a análise de fluxo e salvar `analise.json`. A opção 1 compila e executa o novo exemplo de demonstração.

A análise e a otimização ainda **não** implementam SSA real, ponteiros, heap, otimização global, seleção avançada de registradores ou segurança geral de memória. Veja [detalhes de fluxo de dados e O2](docs/FLUXO_DADOS_RS_0_11.md).

## RS 0.10 — AST localizável e CFG

A RS continua com comandos **sem acentos**, inclusive `inicio` e `senao`. Textos e comentários continuam aceitando UTF-8. Esta atualização não muda a sintaxe pública ou a geração de instruções nativas.

Agora cada token possui **linha e coluna**, e os nós das expressões e instruções da AST preservam essa origem, incluindo blocos aninhados. O compilador também preserva as posições na IR tipada, mesmo quando otimiza constantes.

**Novas opções de análise:**

```powershell
py -3 compilar.py exemplos\fluxo.rts --alvo windows --mostrar-ast --mostrar-cfg --salvar-cfg fluxo.dot -o roteiro_windows.exe
.\roteiro_windows.exe
```

- `--mostrar-ast` apresenta a árvore de instruções e expressões com suas posições originais.
- `--mostrar-cfg` lista os blocos e caminhos do fluxo de controle (`verdadeiro`, `falso`, `continue`, `pare`, `proximo`).
- `--salvar-cfg fluxo.dot` exporta o diagrama no formato DOT, que pode ser aberto com Graphviz. **O Graphviz não é necessário para compilar ou executar o RS.**
- Erros de caracteres, instruções desconhecidas e expressões inválidas passam a indicar linha e coluna e exibir um `^` apontando o local no terminal.
- O menu `INICIAR_RS.bat` ganhou a **opção 5** para ver a AST e o CFG e salvar o DOT; as outras opções continuam funcionando.

**Importante:** o CFG **apenas analisa** o programa. Não implementamos ainda SSA, otimizações globais de caminhos nem um novo backend. O backend continua gerando código nativo, com as mesmas regras da 0.9. Mantivemos testes de igualdade **byte a byte dos 36 executáveis** registrados como referência (9 exemplos × 2 plataformas × 2 níveis de otimização). Consulte [o guia técnico do CFG](docs/CFG_RS_0_10.md).

**Exemplo:** `exemplos/fluxo.rts` usa `para`, `se`, `continue`, `pare` e `enquanto` e imprime 12 e 2 após o texto de demonstração.

## RS 0.9 — Reestruturação interna sem mudar a linguagem

O compilador foi dividido em dois pacotes reais: `compilador/` (léxico, expressões, parser, semântica, tipos, AST, IR e otimizador) e `backend/` (emissão AMD64 e empacotamento PE/ELF). Os arquivos antigos `sintaxe.py`, `ir.py` e `codigo_nativo.py` continuam acessíveis para compatibilidade, mas delegam as operações aos novos pacotes.

A **RS 0.9** não implementava CFG, SSA, ponteiros, heap ou registradores otimizados. A RS 0.10 acrescenta CFG apenas de análise. A IR permanece tipada, o dobramento de constantes existente foi isolado em `compilador/otimizador.py`, e o backend ainda recebe a AST legada por meio de um adaptador. O objetivo foi preparar o projeto para evoluções sem alterar o comportamento atual.

- [Arquitetura detalhada e fronteiras dos módulos](docs/ARQUITETURA_RS_0_9.md)
- [Especificação provisória da linguagem](docs/ESPECIFICACAO_RS_0_9.md)
- [Snapshots de binários da RS 0.8](testes/fixtures/rs08_binarios.json) usados como proteção contra regressões.

Comandos e identificadores continuam **sem acentos**. Strings e mensagens podem usar UTF-8. Abra `INICIAR_RS.bat` no Windows para compilar e executar `exemplos/arquitetura.rts`, que mostra uma contagem tipada e imprime 60.

## Novo na RS 0.8: estouro verificado e IR tipada

```text
inicio {
    seja valor: inteiro = 9223372036854775807
    escreva(valor + 1) // erro de estouro aritmético; código de saída 1
}
```

- **Soma, subtração, multiplicação e negação unária** agora verificam estouro de inteiro com as flags de máquina do x86-64 (`OF`, salto `jo`) e terminam com mensagem e código de saída 1.
- **O menor valor válido**, `-9223372036854775808`, continua permitido, inclusive sem otimização. Negar esse valor *depois* da criação é um estouro e produz erro.
- As proteções anteriores de **divisão por zero** e de `-9223372036854775808 / -1` permanecem. A atualização interna do contador `para` é uma exceção intencional: ao atingir overflow, o laço termina sem gerar erro.
- Nova **IR tipada** em `ir.py`, com nós imutáveis para expressões e instruções. O analisador produz uma AST, que é convertida em IR para otimização, e depois traduzida ao backend x86-64 existente. **Ainda não** temos CFG, SSA, alocador de registradores ou análise global de fluxo.
- `-O 0` mantém as expressões sem dobramento de constantes; `-O 1` (padrão) avalia em tempo de compilação **somente contas constantes seguras**. Operações que gerariam estouro ou divisão por zero continuam executadas com verificação nativa. Não alteramos a ordem dos comandos nem das leituras.

Exemplo sem entrada: `exemplos/otimizacao.rts`.

No PowerShell:

```powershell
py -3 compilar.py exemplos\otimizacao.rts --alvo windows -O 1 --mostrar-ir -o roteiro_windows.exe
.\roteiro_windows.exe
```

Para comparar com otimizações desativadas, use `-O 0`. Exemplo medido no Linux, com `escreva((2 + 3) * (4 + 5) - 6)`: o ELF completo diminuiu de **676 para 608 bytes** (10,1%). No mesmo exemplo Windows, os dois PE completos ficaram com **2.048 bytes** por alinhamento das seções. **Isso não demonstra ganho de velocidade**, apenas diferença no tamanho do arquivo.

## Mantido desde a RS 0.7: tipos verificados pelo compilador

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

- `inteiro` é um número com sinal de **64 bits**; `logico` é `verdadeiro` ou `falso`, representado por 1 ou 0 nos atuais executáveis.
- `seja idade: inteiro = 17` declara explicitamente o tipo; `seja idade = 17` permanece válido e infere `inteiro`.
- Comparações inferem `logico`. O compilador impede misturar tipos incompatíveis, como somar `verdadeiro + 5` ou atribuir `1` a uma variável `logico`.
- `leia` recebe apenas variáveis `inteiro`; contadores de `para` são inteiros. Para manter os programas antigos compatíveis, `se` e `enquanto` ainda aceitam um inteiro não zero como condição.
- Os **dois tipos ocupam 8 bytes por variável na pilha** na atual implementação, sem ponteiros ou alocação dinâmica. Temporariamente limitamos a **256 variáveis locais**, para evitar ultrapassar páginas de pilha sem sondagem (stack probing) no Windows.
- Um literal positivo acima de 9223372036854775807 é rejeitado, mas -9223372036854775808 é permitido.

Os literais lógicos são escritos sem acentos, como todas as palavras reservadas. `escreva(verdadeiro)` imprime `1` por enquanto, não a palavra `verdadeiro`.

Veja a [especificação de tipos e memória](docs/TIPOS_E_MEMORIA_RS_0_7.md). **Os testes de tipo protegem as operações aceitas; ainda não existe proteção geral de memória ou gerenciamento de ponteiros. Os erros de estouro e divisão já são verificados em tempo de execução.**

## Mantido desde a RS 0.6: `leia` — entrada pelo teclado

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

`leia` recebe **uma variável inteira já declarada**. A entrada aceita números com sinal opcional (`-25`, `0`, `+42`), espaços nas extremidades, LF ou CRLF, e EOF após os dígitos. Uma entrada inválida, vazia ou fora do intervalo de -9223372036854775808 a 9223372036854775807 encerra o programa com código 1. No Linux, a mensagem sai no stderr; no Windows, por enquanto, no stdout. A entrada é lida de `stdin` pela rotina nativa, sem heap ou biblioteca Python. A leitura byte a byte **ainda não está otimizada** para grandes volumes.

**Primeira otimização real:** o compilador gera a menor instrução `mov` disponível que preserve valor e flags, carregando algumas constantes em 5 ou 7 bytes em vez dos 10 bytes de `movabs`. Os endereços das variáveis locais na pilha são calculados por uma função comum. Isso reduz código e risco de erros, mas não significa automaticamente execução mais rápida.

**[Plano técnico: memória, ponteiros, instruções primitivas e otimizações](docs/ARQUITETURA_E_OTIMIZACOES.md)**. Ponteiros brutos, heap e objetos ainda são propostas, não recursos da versão 0.8.

## Executar no Windows

1. Baixe o ZIP ou clone este repositório; instale Python 3 e confira `py -3 --version`.
2. Abra **`INICIAR_RS.bat`**. Escolha **1** para compilar e executar `exemplos/otimizacao.rts` (sem entrada pelo teclado).
3. A opção **2** abre o exemplo no Bloco de Notas; a opção **3** roda os testes; **4** executa o último `.exe` gerado; **0** sai do menu.
4. O antigo `TESTAR_WINDOWS.bat` só executa o binário pronto: apertar uma tecla no final fecha a janela, não inicia outro comando.

Ou pelo PowerShell na pasta do projeto:

```powershell
py -3 compilar.py exemplos\otimizacao.rts --alvo windows -O 1 -o roteiro_windows.exe
.\roteiro_windows.exe
```

No Linux x86-64:

```bash
python3 compilar.py exemplos/otimizacao.rts --alvo linux -O 1 -o roteiro_linux
./roteiro_linux
```

Para rodar a suíte automatizada:

```bash
python3 -m unittest discover -s testes -v
```

## Sintaxe e recursos existentes

- Palavras reservadas e nomes de variáveis **sem acentos**: `inicio`, `seja`, `se`, `senao`, `para`, `enquanto`, `leia`, `escreva`. Textos entre aspas e comentários aceitam UTF-8 normal.
- Declarações tipadas `inteiro` e `logico`, inferência com `seja`, verificação estática das atribuições e literais `verdadeiro`/`falso`.
- Inteiros de 64 bits, `+`, `-`, `*`, `/`, `%`, parênteses, atribuição e comparações.
- `inclua matematica`: `somar`, `subtrair`, `multiplicar`, `dividir` e `resto`.
- Decisões com `se` / `senao`; laços `enquanto` e `para numero de 1 ate 5 passo 1`, com `pare` e `continue`.
- Entrada de inteiros com `leia(nome)` e saída de números e textos com `escreva(...)`.
- Código nativo para Windows x86-64 e Linux x86-64, com testes que exercitam programas reais.

## Limitações importantes

Não temos ainda números decimais, entrada de textos, funções definidas pelo usuário, listas, ponteiros, alocação dinâmica, gerenciador de memória, interfaces gráficas ou bibliotecas de jogos. Variáveis precisam ser declaradas fora de blocos nesta versão. Soma, subtração, multiplicação e negação têm detecção de estouro em tempo de execução. No Windows, o backend tem seções fixas de 4 KiB e não foi auditado para distribuição profissional. O verificador de tipos desta versão é apenas o primeiro passo; precisamos de análise de tempo de vida, limites e representação de memória antes de oferecer ponteiros de baixo nível.

## Organização

- `sintaxe.py`: analisador léxico, sintático e verificação inicial de tipos.
- `ir.py`: IR tipada e otimização de constantes conservadora.
- `codigo_nativo.py`: instruções AMD64 e geração de executáveis PE/ELF.
- `bibliotecas/matematica.py`: mapeamentos da biblioteca matemática.
- `compilar.py`: comando de compilação.
- `testes/`: testes unitários, execução nativa e limites de entrada.
- `exemplos/otimizacao.rts`: exemplo da RS 0.8; `tipos.rts` e demais exemplos preservados.
- `docs/ARQUITETURA_E_OTIMIZACOES.md`: arquitetura e próximos passos.

**Prioridades futuras após a RS 0.14:** baixar os nós `phi` em cópias nas arestas, testar equivalência e experimentar alocação de registradores. Buffers de entrada, tipos compostos e segurança de memória continuam pendentes. Licença ainda não definida.
