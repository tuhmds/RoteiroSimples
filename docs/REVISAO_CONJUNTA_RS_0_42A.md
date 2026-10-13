# Revisão conjunta da RS 0.42A.1 a 0.42A.3

Revisão realizada em 13/10/2026 sobre as entregas de propriedade, texto e
bytes. O usuário autorizou integrar o conjunto depois da verificação.
A sequência de dependências é [PR #2](https://github.com/tuhmds/RoteiroSimples/pull/2),
[PR #3](https://github.com/tuhmds/RoteiroSimples/pull/3) e
[PR #4](https://github.com/tuhmds/RoteiroSimples/pull/4). A integração preserva
os commits existentes; não requer reescrever as branches nem eliminar seus históricos.

## Escopo verificado

Contrato/disposição de tipos, parser, tipagem, temporários, transferência e
descarte por escopo; crescimento e cópia, UTF-8 e dados binários; persistência
nativa e seus limites; orçamento de pilha, alinhamento e ABI; `.pdata`/`.xdata`
e desenrolamento Windows real; efeitos e seleção conservadora de O0 a O8;
bibliotecas, aplicações e testes das três entregas. As PRs estavam sem
conflitos, sem comentários de revisão pendentes e com CI aprovada para seus
respectivos commits antes desta revisão.

Proprietários continuam sendo transferidos por três palavras do descritor,
sem copiar o conteúdo. Empréstimos não escapam nem alteram donos. Reserva,
crescimento e descarte são compartilhados entre listas, texto e bytes.
Os testes de transporte observam o mesmo ponteiro, alocações/liberações
corretas, oito registradores inteiros, dez vetoriais e RSP preservados.
Os testes de exceção Windows e regressões da 0.41.5 continuam presentes.

## Achados corrigidos

### Leitura de teclado em índice binário

`leia(dados[0])`, com `bytes` ou `bytes[N]`, era aceito pelo parser e chegava
ao gerador de lista fixa com tamanho interno textual. A compilação terminava
com erro Python de argumento não inteiro. Essa forma de leitura não fazia
parte da API implementada de bytes. O parser agora rejeita com diagnóstico
da linguagem: leia um inteiro e atribua o byte explicitamente. A atribuição
continua verificando o intervalo 0 a 255. A regressão inclui bytes dinâmicos,
fixos e campos binários de registro. Leitura de arquivo completo permanece disponível.

### Empréstimos de lista sem proprietários instanciados

Uma função de consulta definida sobre `emprestimo[lista]`, mesmo não chamada,
podia emitir referências a `erro_lista_liberada` e `erro_indice_lista` sem
que esses diagnósticos fossem gerados. O código considerava somente donos
ou listas fixas ao decidir a emissão. A detecção agora inclui os empréstimos,
preservando as regras distintas de descarte. Não há alocação na entrada do
programa: as rotinas continuam chamadas apenas quando necessárias.

A regressão compila os dois alvos e executa nativamente O0/O8 com funções
que só definem empréstimos de listas inteiras/lógicas, texto ou bytes.
As funções não são chamadas sem uma origem válida; a declaração válida
também não deve provocar referência interna desconhecida ao compilar.

Ambas as correções foram enviadas em
[c5df291](https://github.com/tuhmds/RoteiroSimples/commit/c5df2911770795284e2611d6939795d418bb91e3).
Também foram removidas linhas vazias extras no fim de dois módulos;
`git diff --check` passou no conjunto revisado.

## Resultados

A [CI das correções](https://github.com/tuhmds/RoteiroSimples/actions/runs/38393807039)
executou o commit `c5df291` nos dois sistemas, sem falhas. O processo de
push também foi aprovado. Cada sistema executa seu próprio binário nativo;
gerar ELF no Windows não conta como execução Linux.

| Ambiente | Encontrados | Aprovados | Ignorados | Falhas |
|---|---:|---:|---:|---:|
| Windows local | 569 | 556 | 13 | 0 |
| Windows x64 na CI | 569 | 557 | 12 | 0 |
| Linux x86-64 na CI | 569 | 543 | 26 | 0 |

Os dois testes adicionados pela revisão não são ignorados em nenhuma
plataforma. Os 26 ignorados no Linux incluem ensaios exclusivos da API
Windows. Há um ignorado local adicional por permissão de link simbólico.

Na primeira execução completa local, a remoção de um executável temporário
terminou com `PermissionError` após as verificações do teste. Não foi
identificada falha no resultado do programa. O teste específico passou ao
repetir e a suíte completa foi repetida: 569 testes, zero falhas, 13 ignorados.
Nenhuma asserção foi desativada e nenhum erro de teste foi ocultado.

## Condições e limites da integração

Integrar as PRs na ordem, redirecionando as dependentes para main depois de
cada base integrada. O merge deve conferir o SHA revisado de cada PR.
O conteúdo final da main deve coincidir com o conteúdo testado e sua CI
deve passar novamente no Windows e Linux. As branches são preservadas.

Não foram identificados outros problemas que impedissem integrar o conjunto
após as duas correções. A aprovação se limita aos recursos e provas descritos.
Permanecem pendentes proprietários dentro de registros/listas, empréstimos
mutáveis, fatiamento, APIs posicionais com buffers dinâmicos, falhas recuperáveis,
ampliação da IR, operadores lógicos, reais/decimais e autocompilação.
`HIGH_ENTROPY_VA` permanece desativado. A RS continua experimental.
