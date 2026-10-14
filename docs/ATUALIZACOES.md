# Atualizações da RoteiroSimples (RS)

Índice das entregas técnicas verificáveis. A RS permanece **experimental**: uma versão registrada não significa que a linguagem está pronta para produção. Os detalhes de implementação, testes e limitações de cada etapa estão nas notas vinculadas. A entrada atual do compilador é `compilar.py`, e a versão documentada é **0.42Q**.

## Revisões recentes

| Marco | Evolução | Documentação |
| --- | --- | --- |
| **0.42Q** | Custos internos de IR/SSA, buscas de alcance e fila mínima de phi com equivalência à versão anterior | [Nota técnica](ANALISE_SSA_RS_0_42Q.md) |
| **0.42P** | Medições de crescimento da compilação e compactação de saltos com bytes preservados | [Nota técnica](CONSOLIDACAO_CRESCIMENTO_RS_0_42P.md) |
| **0.42O** | Operadores `e`, `ou` e `nao` com curto-circuito, preservando efeitos e erros observáveis | [Nota técnica](OPERADORES_LOGICOS_RS_0_42O.md) |
| **0.42N** | Retomada coordenada de cadastro experimental entre processos cooperantes | [Nota técnica](RETOMADA_COORDENADA_RS_0_42N.md) |
| **0.42M** | Conversão UTF-8 explícita e cadastro persistente de conteúdo variável | [Nota técnica](CADASTRO_PERSISTENTE_RS_0_42M.md) |
| **0.42L** | SSA, propagação entre blocos e alocação nativa nas funções escalares elegíveis | [Nota técnica](SSA_FUNCOES_RS_0_42L.md) |
| **0.42K** | Fluxo e efeitos de funções escalares, inclusive chamadas e recursão | [Nota técnica](FLUXO_FUNCOES_RS_0_42K.md) |
| **0.42J** | Consolidação de IR, oráculos diferenciais, cobertura e medições | [Nota técnica](CONSOLIDACAO_RS_0_42J.md) |
| **0.42I** | Consulta de registros proprietários por empréstimos de leitura | [Nota técnica](EMPRESTIMOS_REGISTROS_RS_0_42I.md) |
| **0.42H** | Coleções de registros proprietários, movimentação e descarte | [Nota técnica](COLECOES_PROPRIETARIAS_RS_0_42H.md) |
| **0.42G** | Resultados tipados que transportam propriedade e propagam falhas | [Nota técnica](RESULTADOS_PROPRIETARIOS_RS_0_42G.md) |
| **0.42F** | Registros proprietários recebidos e devolvidos por funções | [Nota técnica](REGISTROS_EM_FUNCOES_RS_0_42F.md) |
| **0.42D** | Campos dinâmicos proprietários em registros locais | [Nota técnica](REGISTROS_PROPRIETARIOS_RS_0_42D.md) |
| **0.42C** | Biblioteca de análise lexical escrita na própria RS | [Nota técnica](LEXICO_NATIVO_RS_0_42C.md) |
| **0.42A.3** | Bytes dinâmicos e transferência explícita | [Nota técnica](BYTES_DINAMICOS_RS_0_42A_3.md) |
| **0.42A.2** | Texto UTF-8 dinâmico | [Nota técnica](TEXTO_DINAMICO_RS_0_42A_2.md) |
| **0.42A.1** | Funções com listas proprietárias e empréstimos de leitura | [Nota técnica](VALORES_DINAMICOS_RS_0_42A_1.md) |
| **0.41.5** | Verificação de desenrolamento Windows por mecanismos reais do sistema | [Nota técnica](DESENROLAMENTO_REAL_WINDOWS_RS_0_41_5.md) |

Para o histórico extenso, incluindo marcos intermediários e anteriores, consulte o [README completo](../README.md) e as demais [notas técnicas](./).

## Como ler os resultados

- Os **executáveis produzidos** são nativos para Windows e Linux x86-64, mas o compilador de desenvolvimento **ainda é escrito em Python**.
- O fato de uma função aparecer na linguagem **não** significa que todos os níveis de otimização `-O 0` até `-O 8` usem o mesmo caminho: o compilador ainda tem um caminho conservador para recursos fora do subconjunto otimizado.
- As notas informam as condições efetivamente ensaiadas e os limites conhecidos. Números de testes de um marco histórico não atestam, por si sós, a situação de todos os commits posteriores.
- Persistência e armazenamento são experimentais. Não há reivindicação de conformidade ACID nem recomendação de uso em produção.

## Próximos objetivos

1. Expandir e unificar a representação intermediária, os tipos, os efeitos e o gerenciamento de propriedade, mantendo invariantes verificáveis.
2. Melhorar geração nativa e otimizações sem mudar comportamento observável.
3. Completar funcionalidades práticas e bibliotecas escritas na própria RS, inclusive ferramentas de dados.
4. Criar o RS Studio e ferramentas de aprendizagem em português brasileiro.
5. Preparar, a longo prazo, uma cadeia autocompilável escrita na própria RS, com validação cruzada e sem dependências externas obrigatórias de compilação.

**Contribua:** leia as [regras de contribuição](../CONTRIBUTING.md), os [princípios da RS](PRINCIPIOS_RS.md) e o [convite à avaliação técnica do compilador](CONVITE_REVISAO_TECNICA_COMPILADOR.md).

A RS é desenvolvida com **apoio intensivo de inteligência artificial** na implementação e documentação. Isso não substitui revisão humana, testes independentes nem verificação reproduzível.
