# RS 0.40B — Política uniforme de abertura de arquivos

## Objetivo

Reduzir uma inconsistência concreta: as operações antigas
`grave_arquivo` e `grave_trecho` tinham políticas de abertura
diferentes das de recursos `arquivo` introduzidos depois.
Isso permitia seguir um link simbólico no componente final do nome
em sistemas onde ele estivesse presente.

A nova política é compartilhada pelas APIs novas e legadas **sem
introduzir C, LLVM, Python ou bibliotecas de execução obrigatórias
nos executáveis**. O compilador continua sendo Python; o código gerado
continua nativo Windows/ELF.

## APIs abrangidas

- `grave_arquivo` e `carregue_arquivo` (comandos históricos);
- `grave_trecho` e `carregue_trecho` (acesso posicional);
- `abra_arquivo` em leitura, alteração e criação exclusiva;
- caminhos literais de todas essas APIs passam pela mesma
  função de validação em `compilador/validacao_caminhos.py`;
- `abra_arquivo` com nome variável em `texto[N]` mantém a
  validação nativa já existente, anterior à abertura.

## Linux x86-64

Todos os caminhos de abertura dessas APIs incluem `O_NOFOLLOW`
e `O_CLOEXEC`, definidos centralmente em
`backend/politica_caminhos.py`. `O_NOFOLLOW` recusa o link
simbólico quando ele é o **componente final** do caminho;
`O_CLOEXEC` pede que o descritor não seja herdado após `exec`.

A escrita histórica `grave_arquivo` conserva a semântica
de truncar um arquivo regular, porém não consegue truncar
o destino de um link simbólico final.

## Windows x64

Todas as três famílias de abertura usam
`FILE_FLAG_OPEN_REPARSE_POINT`, para impedir a travessia
automática do ponto final de nova análise, e consultam
`GetFileInformationByHandleEx(FileAttributeTagInfo)` no
**identificador aberto**. Se o objeto apresentar atributo de
diretório ou `FILE_ATTRIBUTE_REPARSE_POINT`, o acesso é recusado.

Na API histórica de gravação integral, o modo de criação passou
de `CREATE_ALWAYS` para `OPEN_ALWAYS`, com `SetEndOfFile`
**somente depois da verificação**. Isso evita truncar o arquivo
antes de confirmar o identificador.

Em comandos de acesso posicional, a recusa de link final gera
estado recuperável `-1`, de abertura; não `-3`, de posição
ou argumento. Na API `arquivo` o retorno de abertura continua
`-1`; a API histórica integral encerra com diagnóstico.

## Garantias que NÃO estão implementadas

**Isso não é uma sandbox de arquivos.**

- A política protege o **componente final** do caminho aberto;
  não resolve nem restringe links em diretórios ancestrais.
- Não existe ainda um diretório-base com identificador estável
  e resolução protegida de todos os componentes em ambas as
  plataformas. O diretório de execução e seus ancestrais devem
  ser confiáveis.
- Links rígidos (hard links), alternância de diretórios e pontos
  de montagem não recebem isolamento completo.
- `publique_arquivo` renomeia entradas; a política de
  `O_NOFOLLOW` não transforma automaticamente uma operação
  de renomeação em uma publicação segura contra adversários
  com acesso de escrita ao diretório.
- Arquivos já abertos com um identificador legítimo podem ser
  modificados por processos que tenham outras permissões;
  as políticas de bloqueio anteriores continuam cooperativas
  no Linux.
- Não prometemos isolamento ACID, transação, recuperação após
  queda de energia, nem resistência a modificações hostis
  simultâneas do diretório.

Uma futura etapa deve criar um objeto de **diretório de confiança**,
validar cada componente sem atravessar links, e fazer criação,
abertura, publicação e sincronização sempre relativas a esse
objeto. Linux pode empregar `openat2` quando disponível; Windows
precisa tratar reparse points e identificadores de diretório
sem depender exclusivamente de validações prévias por nome.

## Testes

`testes/test_politica_caminhos_rs040b.py` executa os
binários nativos e cria um link no diretório de trabalho para
um arquivo externo. Cada uma das três APIs deve recusar
leitura/gravação através do link, sem modificar o conteúdo
externo, em `-O 0` e `-O 8`.

O mesmo teste confirma que arquivos regulares ainda podem
ser lidos, escritos e truncados pela API histórica.
Se o sistema não permite criar links simbólicos, o caso
específico é ignorado explicitamente, em vez de declarado
aprovado sem execução.

Esses testes comprovam o comportamento nesses cenários.
Não provam ausência de falhas de segurança no sistema de arquivos.
