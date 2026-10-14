# RS 0.42N — Retomada coordenada de cadastro em RS

Esta etapa experimental acrescenta `padrao/cadastro_retomada.rts`, escrito
em RS, e três executáveis independentes. O cadastro completo fica em duas
cópias alternadas, com geração, marcador de confirmação e trava estável.
A leitura escolhe a geração válida mais recente; a gravação exige a geração
que o chamador leu, para recusar uma atualização obsoleta. O compilador
acrescenta `consulte_arquivo` para distinguir ausência de falha de acesso.

O protocolo é uma prova para o Dados RS, sem transações gerais, WAL, índices
ou garantias ACID. Seu formato é experimental e não congela o futuro motor.
Os testes de encerramento forçado verificam interrupção do processo; não
demonstram durabilidade absoluta após perda de energia.

## Arquivos e coordenação

Os nomes são fixos, relativos ao diretório corrente:

| Arquivo | Papel |
|---|---|
| `cadastro_a.rsd` | cópia de índice `0` |
| `cadastro_b.rsd` | cópia de índice `1` |
| `cadastro_trava.rsl` | recurso de trava, conservado entre operações |

`carregar`, `inicializar` e `salvar` abrem a mesma trava em modo `alteracao`
e pedem bloqueio exclusivo não bloqueante. A trava permanece aberta durante
toda a operação, inclusive validação, escolha da cópia e escrita. Contenção
ou falha de abertura/bloqueio devolve `40`; o chamador decide quando repetir.
O bloqueio é liberado ao sair do escopo ou quando o sistema encerra o processo.

Todos os processos devem cooperar com esse protocolo, executar no mesmo
diretório e conservar a identidade do arquivo de trava. Não remova, substitua
ou renomeie a trava enquanto houver usuários. A exclusividade por abertura
no Windows e `flock` no Linux seguem os limites dos recursos da RS 0.39.
A trava não abrange o intervalo entre `carregar` e `salvar`: a comparação de
geração sob trava impede que esse intervalo produza sobrescrita silenciosa.

## API e propriedade

```text
importe "padrao/cadastro_retomada.rts" como disco
importe "padrao/cadastro_variavel.rts" como cad
```

| Função pública | Retorno e comportamento |
|---|---|
| `carregar() -> Leitura` | valida as duas cópias sob trava e devolve um cadastro proprietário |
| `inicializar() -> Gravacao` | somente com as duas cópias ausentes, grava cadastro vazio na cópia `0`, geração `1` |
| `salvar(cadastro: emprestimo[cad.Cadastro], geracao_esperada: inteiro) -> Gravacao` | revalida o estado atual sob trava, compara a geração, serializa e grava na outra cópia com geração atual mais `1` |

`Leitura` contém `valido: logico`, `codigo_erro: inteiro`, `geracao: inteiro`,
`copia: inteiro`, `recuperado: logico` e `valor: cad.Cadastro`. Consulte os
dados e metadados somente quando `valido` for verdadeiro. `recuperado` indica
que uma cópia presente, incompleta ou corrompida foi ignorada; a ausência da
outra cópia, por si só, não ativa esse campo. Para consumir o cadastro,
use `mova(leitura.valor)`; consultas podem usar empréstimos de seus registros.

`Gravacao` contém `valido`, `codigo_erro` e `geracao`. Código `0` significa
sucesso. Em conflito `46` ou esgotamento `47`, `geracao` é a geração atual.
Em falha anterior à confirmação `43`, ela conserva a geração atual
(`0` na inicialização). Em confirmação `51`, ela é a geração candidata,
sem garantir que esteja confirmada. Uma falha de leitura em `salvar` devolve
geração `0`; uma inicialização recusada devolve a geração lida, quando houve
leitura válida. Falhas de trava devolvem geração `0`.

```text
seja leitura = disco.carregar()
se leitura.valido == falso {
    escreva(leitura.codigo_erro)
    encerre(3)
}
seja cadastro = mova(leitura.valor)
// Altere cadastro com as operacoes de cad e recupere seus resultados.
seja gravacao = disco.salvar(empreste(cadastro), leitura.geracao)
se gravacao.valido == falso {
    escreva(gravacao.codigo_erro)
    encerre(3)
}
```

`salvar` empresta o cadastro, preservando seu dono. Um conflito exige nova
leitura e decisão da aplicação sobre como reaplicar a alteração; não há
mesclagem automática. A comparação de geração é uma atualização condicional
(CAS) protegida pela trava. O protocolo não mantém uma transação aberta entre
as chamadas e não restaura automaticamente o estado em memória do chamador.

## Formato RSCN versão 1

Cada cópia contém um envelope de 40 bytes e, a partir do deslocamento `40`,
um arquivo RSCV completo da RS 0.42M. Inteiros são little-endian; nenhum
ponteiro ou capacidade de memória é armazenado.

| Deslocamento | Campo | Tamanho |
|---:|---|---:|
| 0 | identificação `RSCN` | 4 bytes |
| 4 | versão `1` | u32 |
| 8 | geração, de `1` a `9223372036854775807` | u64 positivo |
| 16 | comprimento do RSCV completo | u32 |
| 20 | Adler-32 do RSCV completo | u32 |
| 24 | Adler-32 dos bytes `0` a `23` do envelope | u32 |
| 28 | reservado `0` | u32 |
| 32 | marcador ASCII `CONFIRMA` | 8 bytes |
| 40 | RSCV versão `1`, com seu próprio cabeçalho e corpo | comprimento declarado |

O corpo RSCV deve ter de 24 a 8388608 bytes. Seus limites permanecem:
até 1024 registros, códigos de `1` a `9223372036854775807`, títulos UTF-8
estritos de 1 a 1024 bytes e conteúdos binários de 0 a 65536 bytes.
Confira o [formato e a biblioteca da RS 0.42M](CADASTRO_PERSISTENTE_RS_0_42M.md).
As duas somas externas e a soma interna detectam corrupção acidental;
Adler-32 não autentica arquivos nem impede uma alteração deliberada.

A abertura em `alteracao` não trunca a cópia. Ao gravar um cadastro menor,
bytes antigos podem permanecer depois do corpo declarado e são ignorados.
O arquivo físico inteiro deve permanecer dentro de 8388648 bytes
(`40 + 8388608`); a leitura verifica o excesso com uma consulta de um byte
nesse limite. Sobras não participam das somas nem da desserialização.
Antes de invalidar o destino, a gravação também verifica seu limite físico.
Se ele já estiver acima desse limite, devolve `43`, conservando a geração
anterior e sem confirmar dados novos. Como esta API não trunca, esse alvo
exige intervenção manual antes de outra gravação. A leitura ainda pode
retomar pela outra cópia válida.

## Escrita e retomada

Depois de validar as cópias, a geração esperada e o cadastro, `salvar` escolhe
a cópia oposta à selecionada pela leitura. A cópia atual permanece intacta.
A rotina de escrita executa estas etapas, sem truncamento ou renomeação:

1. Abre a cópia de destino em `alteracao`, verifica seu limite físico,
   escreve oito zeros no marcador
   e sincroniza o arquivo antes de reutilizar qualquer outro byte.
2. Escreve os 32 bytes iniciais do envelope e o RSCV em blocos de até
   4096 bytes; sincroniza o arquivo novamente.
3. Escreve `CONFIRMA`, sincroniza pela terceira vez e fecha explicitamente.

As sincronizações usam `FlushFileBuffers` no Windows e `fsync` no Linux.
Uma cópia só participa da seleção depois de ter marcador completo,
identificação, versão, geração, comprimentos, reservado, somas e RSCV válidos.
Uma interrupção durante a reutilização pode deixar a cópia de destino
inválida; a outra cópia confirmada permite retomada. Se o marcador completo
já foi escrito, a nova geração pode ser observada após interrupção de processo,
inclusive antes de o chamador receber sucesso.

| Situação na leitura | Decisão |
|---|---|
| Duas cópias válidas, gerações diferentes | seleciona a maior geração |
| Uma válida e outra ausente | seleciona a válida, `recuperado = falso` |
| Uma válida e outra presente inválida | seleciona a válida, `recuperado = verdadeiro` |
| Duas ausentes | falha `44`; somente `inicializar` pode criar o cadastro |
| Nenhuma válida, com pelo menos uma presente inválida | falha `45`; exige intervenção |
| Duas válidas com geração igual | falha `48`, mesmo com conteúdo igual |
| Envelope confirmado RSCN com versão diferente de `1` | falha `49`, mesmo que a outra cópia seja válida |
| Falha de consulta, abertura ou leitura de qualquer cópia | falha da etapa; não é tratada como ausência ou corrupção recuperável |

A rejeição de qualquer versão diferente de `1`, inclusive `0`, ocorre
assim que o marcador e a identificação RSCN são reconhecidos, antes das
somas. Não se presume o formato do restante de uma versão desconhecida.
O campo `recuperado` não indica reparo: `carregar` só seleciona;
uma próxima gravação bem-sucedida reutiliza a cópia inativa.

Antes do primeiro cadastro confirmado não existe cópia anterior para
retomar. Se a primeira inicialização deixar um arquivo parcial, `carregar`
devolve `45` e uma nova `inicializar` devolve `50`. A aplicação deve exigir
inspeção e intervenção explícita, preservando os arquivos para análise;
o protocolo não converte automaticamente esse estado em cadastro vazio.

## Códigos recuperáveis

| Código | Significado |
|---:|---|
| 0 | operação concluída |
| 40 | abertura ou aquisição da trava falhou, incluindo contenção |
| 41 | consulta ou abertura de uma cópia falhou, ou seu tipo foi recusado |
| 42 | leitura ou fechamento explícito de uma cópia falhou |
| 43 | abertura para escrita, verificação do limite físico, invalidação, envelope/corpo ou sincronização anterior à confirmação falhou |
| 44 | as duas cópias estão ausentes |
| 45 | não há cópia válida e existe ao menos uma cópia presente inválida |
| 46 | geração esperada difere da geração atual; nenhuma cópia é escrita |
| 47 | geração atual chegou ao máximo positivo; nenhuma cópia é escrita |
| 48 | duas cópias válidas têm a mesma geração |
| 49 | envelope confirmado RSCN tem versão não suportada |
| 50 | inicialização recusada porque o estado não é de duas cópias ausentes |
| 51 | escrita/sincronização do marcador ou fechamento final falhou; confirmação pode ter ocorrido |

Erros de validação retornados por `cad.serializar` também atravessam `salvar`,
com os códigos do [cadastro da RS 0.42M](CADASTRO_PERSISTENTE_RS_0_42M.md).
Um `43` em uma gravação posterior preserva a cópia atual; uma inicialização
não dispõe dessa proteção. Em `51`, recarregue e confira a geração antes de
decidir repetir. Falta de memória (OOM), dono inativo e falha de fechamento
implícito no descarte seguem o contrato fatal existente. Os códigos acima
não tornam esses casos recuperáveis. A trava é fechada implicitamente no
fim da operação; seus erros de fechamento também seguem esse contrato.

## Consulta de existência

```text
seja estado = 0
consulte_arquivo("cadastro_a.rsd", estado)
```

O caminho deve ser um literal ASCII simples no diretório corrente,
sem separadores, nomes reservados ou componentes de navegação. O estado
deve ser uma variável inteira simples. A consulta não abre nem modifica o
arquivo: `0` indica arquivo aceito, `1` indica ausência e `-1` indica falha
ou tipo recusado. Um `0` não garante permissão para a abertura posterior.

No Windows, a emissão usa `GetFileAttributesA`, recusa diretórios e pontos
de nova análise e só traduz `ERROR_FILE_NOT_FOUND` para ausência. A função
retorna atributos do próprio link simbólico e comunica falha por
`INVALID_FILE_ATTRIBUTES` e `GetLastError`, conforme a
[documentação da Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileattributesa).
No Linux x86-64, usa `newfstatat` com `AT_FDCWD` e `AT_SYMLINK_NOFOLLOW`,
exige `S_IFREG`, repete em `EINTR` e só traduz `ENOENT` para ausência.
Essas opções consultam o nome relativo ao diretório corrente e o link final
sem segui-lo, conforme [stat(2)](https://man7.org/linux/man-pages/man2/stat.2.html).

A consulta é anterior à abertura real e não elimina a corrida entre elas.
O diretório deve ser confiável: alterações externas de nomes, links, arquivos
ou da trava não são cobertas. Não há proteção integral contra links em
componentes ancestrais nem contra escritores que ignorem a coordenação.

## Exemplos e verificação

```text
python compilar.py exemplos/dados_rs/cadastro_inicializar_rs042n.rts --alvo windows -O 8 -o inicializar.exe
python compilar.py exemplos/dados_rs/cadastro_salvar_rs042n.rts --alvo windows -O 8 -o salvar.exe
python compilar.py exemplos/dados_rs/cadastro_reabrir_rs042n.rts --alvo windows -O 8 -o reabrir.exe
./inicializar.exe
./salvar.exe
./reabrir.exe
```

No Linux, use `--alvo linux` e nomes sem `.exe`. Execute os três no mesmo
diretório de trabalho confiável. A inicialização mostra código `0` e geração
`1`. O gravador mostra a geração lida, recebe um inteiro de `0` a `255`,
acrescenta ou altera o registro `7` com título `Ação 🌱` e 6000 bytes e mostra
o código e a geração resultante. O leitor mostra geração, recuperação, quantidade
e campos por empréstimo. Os executáveis gerados não dependem de Python.

As três suítes acrescentam 26 testes: consulta, retomada e ABI Windows.
Usam `struct` e `zlib` como oráculos independentes, verificam O0–O8,
geração obsoleta entre dois processos, trava estável, corrupção,
truncamento, limites, sobras e recusa de versões. Instrumentam a rotina RS
real de escrita e encerram o processo em 11 pontos, incluindo marcadores
parciais, nos níveis O0 e O8. `TerminateProcess`/`SIGKILL` interrompem o
processo sem limpeza RS; o sistema e seu cache continuam ativos. Esses
ensaios não simulam desligamento físico.

No Windows, os ensaios nativos verificam RSP, oito registradores inteiros,
dez vetoriais, desenrolamento, INT3 e balanceamento dos donos em retornos
normais e por erro. Falhas de consulta não viram ausência; falhas de
preparação preservam a geração anterior; falha na sincronização final depois
de escrever o marcador devolve resultado incerto e permite nova leitura.
No Linux, limite de arquivo provoca escrita parcial real.

A suíte local completa Windows/Python 3.14 executou 800 testes, sem falhas,
com 17 ignorados conforme plataforma e privilégios. A validação da entrega
na CI usa Windows/Linux em Python 3.10/3.11/3.14; resultados e relatórios
correspondem ao commit aprovado no GitHub.

## Limites e compatibilidade

O protocolo não implementa sincronização do diretório após criar a trava ou
uma cópia. As sincronizações de arquivo, a ordem das etapas e as verificações
não constituem promessa de sobrevivência absoluta a perda de energia,
falha de hardware, controlador ou sistema de arquivos. Não há diário,
isolamento transacional geral, múltiplas operações atômicas ou reparo de
duas cópias inválidas. Resultado incerto após confirmação exige nova leitura.

O corpo RSCV conserva o formato da RS 0.42M, mas o envelope RSCN e os nomes
de arquivo são diferentes. `padrao/cadastro_arquivo.rts`, `cadastro.rsd` e
`cadastro_provisorio.rsd` continuam disponíveis separadamente, sem migração
automática. Não troque esses arquivos pelas cópias RSCN. Uma migração futura
deve carregar, validar e converter explicitamente, com cópia de segurança.

Donos, empréstimos e arquivos continuam no gerador conservador em O0–O8.
As consultas são lineares e a validação de unicidade é quadrática. A leitura
pode manter os cadastros das duas cópias; a serialização, desserialização e
montagem dos buffers criam cópias adicionais. O limite de 8 MiB do RSCV não
é um orçamento total de memória do processo. Orçamento de memória,
sincronização de criação, testes de falhas do sistema e de perda de energia
e regras de migração permanecem necessários antes de ampliar as garantias.
