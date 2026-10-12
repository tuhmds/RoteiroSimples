# Contrato entre a RoteiroSimples e o Dados RS — plano inicial

**Situação:** especificação de arquitetura, não implementação de banco de dados.

## 1. Decisão de produto

O **Dados RS** será um projeto e repositório próprios, com código do motor e
das interfaces escrito primordialmente em RoteiroSimples. A RoteiroSimples
continuará sendo a linguagem e o compilador; não incorporaremos o motor de
banco de dados ao compilador.

O produto terá dois modos independentes e complementares:

1. **Banco próprio/embarcado:** executa consultas sobre arquivos `.rsd`,
   sem PostgreSQL, SQLite ou MariaDB instalados.
2. **Cliente de outros motores:** acessa bancos preexistentes por conectores
   com uma interface RS compartilhada, sem substituir o processamento e as
   garantias do banco remoto.

Um terceiro modo, **servidor Dados RS**, virá após o motor embarcado, com
protocolo, autenticação, sessões e concorrência.

## 2. Organização prevista para o repositório RS-Dados

- `nucleo/`: contratos, representação de valores, mensagens de erro e tipos.
- `motor/`: formato de arquivo, páginas, catálogo/esquemas, registros,
  índices, gerenciamento do armazenamento, transações, diário e recuperação.
- `consultas/`: análise sintática, validação, planejamento, execução e
  parametrização das consultas.
- `conexoes/`: contrato dos conectores e adaptadores de SQLite,
  PostgreSQL e MySQL/MariaDB.
- `gestor/`: interface administrativa local e, futuramente, visual.
- `testes/`: propriedades, corrupção, interrupção de processos, reinício,
  compatibilidade e comparação com outros motores.
- `exemplos/`: cadastro de entregas, estoque, diário escolar e relatórios.

Os arquivos controlados pelo projeto usam nomes técnicos em português
brasileiro e comandos RS sem acentos.

## 3. Formato próprio v1 — proposta a validar

- Extensão principal `.rsd` e diário `.rsj`.
- Identificação e versão explícitas no cabeçalho; rejeitar versões desconhecidas.
- Páginas de tamanho fixo configurado na criação (primeira proposta: 4096 bytes).
- Ordem de bytes e tipos serializados definidos independentemente da CPU.
- Catálogo de tabelas, colunas, tipos, restrições e versões de esquema.
- Identificador estável de registro; dados e metadados em páginas distintas.
- Verificação de integridade por página, tamanhos antes da leitura e limites
  de alocação; nenhum ponteiro de memória no formato armazenado.
- **Primeiro mecanismo de escrita:** registros acrescentados ao final e
  reconstrução controlada do estado no reinício, antes de índices em disco.
- Atualizações e exclusões devem ter identificação e regras de recuperação.
- A organização por páginas e o índice em árvore serão incrementais.

Nenhum formato binário está congelado antes de testes de retomada e migração.

## 4. Transações e integridade

Primeiro objetivo: um gravador por banco e leitores coordenados, com
`inicie_transacao`, `confirme`, `desfaca`. Um diário de gravação
anterior (WAL ou mecanismo equivalente) deve registrar alterações e o
marcador de confirmação. O motor reinicia após interrupções, reaplica
operações confirmadas, descarta as incompletas e verifica integridade.

**Não declarar ACID/durabilidade real** sem sincronização de dados e
metadados no disco, trava de concorrência, testes de desligamento abrupto e
documentação das garantias por plataforma.

## 5. Consultas

Linguagem própria em português, sem acentos obrigatórios. Exemplos
**de sintaxe proposta, ainda não aceitos pelo compilador**:

```text
CRIE TABELA entregas (codigo INTEIRO, distancia INTEIRO)
INSIRA EM entregas (codigo, distancia) VALORES (101, 3)
CONSULTE codigo, distancia DE entregas ONDE distancia > 2
ATUALIZE entregas DEFINA distancia = 4 ONDE codigo = 101
EXCLUA DE entregas ONDE codigo = 101
```

Internamente: analisador -> árvore de consulta -> verificação de esquema ->
plano -> operador de execução. O motor local entende essa linguagem; os
conectores externos podem receber SQL convencional no dialeto do destino.
Não prometer tradução universal automática entre dialetos.

Consultas parametrizadas, tipos, limites e valores separados do texto da
consulta são exigidos desde o início para evitar injeção de comandos.

## 6. Interface de conexão comum — contrato a implementar

- `abra_conexao` / `feche_conexao`
- `prepare_consulta` / `defina_parametro` / `execute_consulta`
- `proxima_linha` / `leia_coluna`
- `inicie_transacao` / `confirme_transacao` / `desfaca_transacao`
- `obtenha_esquema` / `obtenha_capacidades` / `obtenha_erro`

Esses nomes descrevem o contrato futuro: **não são funções disponíveis na
versão atual**. Resultados devem informar explicitamente sucesso ou falha,
sem encerrar o processo por todo erro recuperável.

O motor local implementará essa interface. Adaptadores usarão interfaces
nativas suportadas pelo destino: `libsqlite3` para SQLite, `libpq` para
PostgreSQL e `libmariadb` para MySQL/MariaDB, quando possível, por uma
ponte ABI C gerada pela RS. As bibliotecas e protocolos externos seguem
seus nomes exigidos pela compatibilidade. Conectores deverão verificar
recursos disponíveis (transações, parâmetros, esquemas, retornos, tipos,
TLS etc.) e normalizar diagnósticos, não resultados incompatíveis.

## 7. Requisitos que cabem à linguagem RS

A RS 0.34 oferece `grave_arquivo` e `carregue_arquivo` para `texto[N]`.
A RS 0.35 acrescenta `grave_trecho` e `carregue_trecho`: acesso binário
posicional em 64 bits, sem truncamento total e com retorno numérico
recuperável (-1, -2, -3, -4). Sua implementação usa chamadas nativas
diferentes no Linux e Windows e inclui testes de conteúdo binário e de
persistência entre processos.

**Ainda não basta para um banco confiável:** não existe `fsync`/
`FlushFileBuffers`, transação, travamento, abertura persistente nem
abstração tipada de bytes e erros. `texto[N]` continua sendo o buffer
temporário, não um tipo de sequência binária.

Prioridades que deverão ser implementadas e validadas na linguagem/núcleo:

1. Bytes e sequências binárias tipadas; **leitura/escrita por posição em
   64 bits implementadas na RS 0.35**, ainda usando `texto[N]`.
2. Identificadores de arquivo com tempo de vida seguro; operações parciais
   já suportadas pelos comandos posicionais, mas ainda faltam abertura
   persistente e codificação explícita de valores.
3. Erros recuperáveis já disponíveis como códigos inteiros na RS 0.35;
   evoluir para resultados tipados (`resultado[T]`).
4. Sincronização durável, substituição atômica, travamento e modos de
   compartilhamento documentados em Windows e Linux.
5. Texto dinâmico ou buffers dimensionados seguros para consultas e campos.
6. Interface de funções externas (ABI C) para drivers existentes.
7. Rede, TLS e gerenciamento de credenciais para modo servidor e clientes
   remotos, quando necessário.

Os recursos de sistema podem usar chamadas nativas inevitáveis; a lógica
do banco e dos conectores permanece escrita em RS.

## 8. Sequência de entregas e condições de aceite

- **Fase A — pré-requisitos da RS:** operações binárias e erros
  recuperáveis com testes nativos em Windows/Linux.
- **Fase B — Dados RS embarcado mínimo:** criar, inserir, listar, reiniciar,
  ler registros corretamente e rejeitar arquivos inválidos; comparações e
  buscas lineares inicialmente.
- **Fase C — esquema e índices:** tipos, restrições, busca por chave e
  comparação de plano sequencial vs. índice.
- **Fase D — transações:** diário, confirmação, rollback e recuperação de
  falhas/interrupções reproduzíveis.
- **Fase E — consultas:** análise PT-BR, expressão de filtros, projeção,
  ordenação, parâmetros e plano de execução.
- **Fase F — conectores:** primeiro SQLite por ABI; depois PostgreSQL;
  depois MySQL/MariaDB, com suítes de contrato idênticas.
- **Fase G — servidor e gestor:** múltiplos clientes, autenticação,
  controle de acesso, painel administrativo e importação/exportação.

**Primeira prova real:** dois programas RS diferentes abrem o mesmo
`.rsd` em execuções consecutivas; um cadastra 100 entregas, o outro
recupera os 100 registros com valores corretos. Um arquivo truncado é
rejeitado com diagnóstico e não causa acesso fora dos limites.

Não chamar esse marco de SQL, transacional ou ACID antes da implementação
efetiva dos módulos correspondentes.

## 9. Limites e decisões pendentes

Definir separadamente versão de formato, compatibilidade de esquema,
restrições de concorrência, estratégia de cópias de segurança, tamanhos
máximos por coluna, codificação UTF-8, representação monetária exata,
índices e migrações. Jamais afirmar que a integração com PostgreSQL/MySQL
é completa antes dos testes de versão e de tipos de cada driver.
