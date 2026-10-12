# RS 0.34 — Leitura e gravação de arquivos

## Comandos

- \`grave_arquivo("caminho.txt", conteudo)\`: cria ou substitui o arquivo,
  escrevendo exatamente os bytes válidos de \`conteudo: texto[N]\`.
- \`carregue_arquivo("caminho.txt", conteudo)\`: lê o conteúdo integral para
  \`conteudo\` e atualiza seu tamanho, incluindo arquivos vazios.

## Segurança e regras

A capacidade é verificada com uma leitura extra de um byte quando o arquivo
alcança o limite. Se houver dados adicionais, a execução é encerrada com um
erro explícito; não há truncamento silencioso. Falhas de sistema são erros
controlados e nenhum sucesso parcial é ocultado. Gravadores repetem escritas
parciais; leitores repetem leituras parciais até atingir o fim do arquivo.
No Linux, chamadas interrompidas pelo sistema (\`EINTR\`) são repetidas.

Na primeira etapa o caminho é literal, relativo ao diretório do processo,
até 240 caracteres ASCII e sem segmentos \`.\` ou \`..\`. Diretórios
intermediários precisam existir. Não são suportados caminhos absolutos,
caminhos calculados, compartilhamento de handles ou diretórios automáticos.
No Windows são usadas \`CreateFileA\`, \`ReadFile\`, \`WriteFile\` e
\`CloseHandle\`. No Linux usam-se diretamente \`openat\`, \`read\`,
\`write\` e \`close\`.

O comando de gravação *substitui* o arquivo existente e não é transacional:
uma falha ou término abrupto pode deixar um arquivo parcial. Para dados
críticos, uma versão futura deve oferecer gravação atômica, erros
recuperáveis e sincronização no disco. O buffer guarda bytes, não verifica
UTF-8 após carregar; não há serialização automática de estruturas.
O compilador segue experimental, não indicado para produção.

## Testes de aceitação

A suíte cobre compilação e execução nos dois sistemas, arquivo inexistente,
vazio, limite exato, excesso de capacidade, persistência entre processos,
tratamento de caminhos inválidos e armazenamento de UTF-8.
