# RS 0.38 — Recursos de arquivo, erros recuperáveis e sincronização

## Finalidade e limites

O código do motor Dados RS precisará abrir um arquivo uma vez, ler e gravar
páginas por posição, sincronizar alterações e fechar recursos mesmo quando
o fluxo sai de um bloco. A RS 0.38 oferece essas primitivas nativamente em
Windows x64 e Linux x86-64, sem Python, C ou LLVM **na execução**.

Esta etapa **não fornece transações, isolamento de processos, cópia atômica,
atualização atômica de arquivo, nem garantias absolutas contra falha de energia**.

## API pública

- \`seja arq: arquivo\`: recurso proprietário inicializado como fechado.
  A variável não pode ser copiada, comparada ou passada por valor.
- \`abra_arquivo("caminho.rsd", arq, "novo", estado)\`: cria somente se
  o arquivo não existir; falha se já existir, **sem truncar**.
- \`abra_arquivo("caminho.rsd", arq, "alteracao", estado)\`: abre para
  leitura/gravação, criando se não existir; não trunca.
- \`abra_arquivo("caminho.rsd", arq, "leitura", estado)\`: abre existente
  somente para leitura.
- \`grave_em(arq, dados, posicao, estado)\`: grava o comprimento atual
  de \`dados: bytes[N]\` desde a posição (64 bits).
- \`carregue_de(arq, dados, posicao, quantidade, estado)\`: lê até
  \`quantidade\` bytes, limitada à capacidade; define o comprimento
  para a contagem retornada. EOF devolve zero.
- \`sincronize_arquivo(arq, estado)\`: solicita ao sistema que sincronize
  o arquivo com o dispositivo, usando \`fsync\` no Linux e
  \`FlushFileBuffers\` no Windows. Verifique o retorno.
- \`feche_arquivo(arq, estado)\`: solicita o fechamento e marca o recurso
  como fechado mesmo diante de erro, para evitar reutilizar um
  identificador cujo destino seja incerto.

Caminhos são **literais ASCII relativos** no RS 0.38, com as mesmas
restrições da RS 0.34/0.35. Não há parâmetros dinâmicos de caminho ainda.

## Estados

| Valor | Significado |
|---|---|
| \`0\` | Sucesso em abrir/fechar/sincronizar; leitura vazia ou operação de zero bytes |
| \`n > 0\` | Quantidade de bytes lidos/gravados |
| \`-1\` | Não conseguiu abrir/criar o arquivo |
| \`-2\` | Falha durante a transferência |
| \`-3\` | Recurso fechado, posição inválida ou quantidade excedida |
| \`-4\` | Falha durante o fechamento |
| \`-5\` | Tentou abrir novamente recurso que já está aberto |
| \`-6\` | Falha durante a sincronização |

A biblioteca oficial \`importe "padrao/arquivos.rts" como arquivos\`
contém \`arquivos.resultado_arquivo(estado)\`, que converte o código
em \`resultado[inteiro]\`: \`valido\`, \`valor\`, \`codigo_erro\`.
O código tipado de falha é a magnitude do estado negativo (1 a 6).
Estados inferiores a -6 tornam-se erro 7 (desconhecido).
**O adaptador é opcional:** os comandos nativos ainda devolvem inteiros,
não um resultado genérico diretamente.

## Duração e propriedade

Um \`arquivo\` não pode ser copiado, atribuído, comparado nem transferido
como parâmetro de função; cada variável é dona de um único identificador.
Reabrir uma variável ainda aberta devolve -5 sem perder o identificador.
Abrir um arquivo inexistente em modo leitura devolve -1 sem encerrar
o processo.

Recursos declarados em blocos são fechados automaticamente ao sair
normalmente, com \`pare\` ou \`continue\`; recursos restantes em funções
são fechados no retorno e ao fim de \`inicio\`. Uma falha em fechamento
implícito é tratada como erro fatal, não ignorada silenciosamente.

\`encerre\` encerra imediatamente o processo; o sistema operacional
fecha os identificadores restantes, **mas esse caminho não sincroniza
automaticamente os dados nem verifica erros de fechamento**. Portanto,
programas que precisam de confirmação de persistência devem chamar
\`sincronize_arquivo\` e \`feche_arquivo\`, verificando os estados,
**antes** de concluir sucesso ou chamar \`encerre(0)\`.

## Implementação

- Linux x86-64: \`openat\`, \`pread64\`, \`pwrite64\`, \`fsync\` e
  \`close\`; novos arquivos com permissão inicial 0600; \`O_EXCL\`
  na criação exclusiva, e \`O_NOFOLLOW\` no componente final do caminho.
- Windows x64: \`CreateFileA\`, \`SetFilePointerEx\`, \`ReadFile\`,
  \`WriteFile\`, \`FlushFileBuffers\` e \`CloseHandle\`. Uma abertura
  Windows impede compartilhamento por outros processos enquanto durar
  o identificador; isso **não equivale** a uma API geral de travas.
- A transferência reitera operações parciais e \`EINTR\` no Linux;
  nenhuma tentativa de leitura ultrapassa a capacidade do buffer.
- A posição de leitura/escrita é explícita; o identificador é usado
  sem compartilhamento manual dentro da RS.

## O que não podemos prometer

\`fsync\` e \`FlushFileBuffers\` solicitam sincronização, mas o resultado
depende da implementação do dispositivo, do sistema de arquivos e da
plataforma. No Linux, criar arquivo com \`fsync\` não sincroniza
necessariamente a entrada no **diretório pai**. Não implementamos
\`fsync\` do diretório, travas multi-processo universais, journaling,
recuperação transacional, nem testes reais de queda de energia.

Linux permite acesso simultâneo por processos independentes ao mesmo
arquivo, inclusive alterações concorrentes; não há isolamento por
páginas. No Windows ainda não tratamos todos os caminhos reparse/symlink
como diretórios confiáveis. Evite caminhos controlados por agentes
hostis ou diretórios compartilhados não confiáveis.

Em caso de erro após uma escrita parcial, os bytes já transferidos
podem permanecer no arquivo; o comando devolve -2 mas não os desfaz.
Aplicações devem implementar journal/rollback para transações reais.

## Próxima etapa

Adicionar criação e atualização atômicas por arquivo temporário,
renomeação e \`fsync\` de diretório quando aplicável; interfaces de
caminhos parametrizáveis com validação; isolamento por trava; testes de
falhas injetadas e formatos binários versionados. Só depois avançar
para páginas, catálogo e recuperação do motor embarcado Dados RS.
