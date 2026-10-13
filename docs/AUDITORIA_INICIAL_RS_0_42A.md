# Auditoria inicial — primeira entrega da RS 0.42A

## Referência reproduzível antes das alterações

Base: `840d308e75a7a5864367c9473741461fdfb2583b`, main com RS 0.41.5. A PR #1 está integrada. Antes de alterar código, a cópia local limpa executou `python -m unittest discover -s testes -v`: 441 testes Windows x64, zero falhas, 13 ignorados por condições de plataforma/permissão. A [integração contínua da main](https://github.com/tuhmds/RoteiroSimples/actions/runs/38325947913) também está aprovada nos dois sistemas.

O relatório local está no arquivo de trabalho `base-rs0415-840d308-windows.txt`. Os geradores PE32+/ELF64 continuam diretos e os executáveis não exigem Python. A fundação de desenrolamento, sondagem, ABI e arquivos da 0.41.5 será mantida e testada.

## Inspeção e reaproveitamento

O léxico conserva identificadores ASCII e literais UTF-8; não precisa ser reescrito para transferências em expressões. O parser e `ContextoSemantico` já mantêm tipos, escopos, nomes internos e temporários compostos. `disposicao_tipos.palavras_tipo` calcula a mesma largura na pilha e no armazenamento de elementos.

As listas proprietárias já têm descritor de três palavras (ponteiro, comprimento, capacidade), crescimento geométrico, alocação nativa, movimentação sem cópia de conteúdo e estado inativo com comprimento negativo. Os empréstimos de leitura são referências temporárias ao descritor e não escapam das funções síncronas. Fechamento de escopo, pare, continue e retorno já descartam recursos determinística e explicitamente.

A ABI interna já passa valores compostos e oferece destino oculto para retorno. Ela será reaproveitada para transferir descritores. As rotinas Windows preservam registradores e possuem metadados verificados; os testes de exceção real da 0.41.5 continuam obrigatórios.

`contrato_efeitos.Efeitos` já representa leitura, escrita, propriedade, controle e falhas observáveis. A estratégia de compilação mantém funções/valores proprietários no caminho conservador: a IR ainda não transporta integralmente funções, registros e propriedade. Não será introduzido O9 nem uma alegação de suporte SSA fictícia.

A biblioteca padrão contém código RS real. O módulo de listas oferece várias funções limitadas a cinco inteiros, mas os empréstimos tipados atuais permitem adicionar consultas gerais em RS sem novo comando especial ou cópia da coleção.

## Falhas e limitações identificadas

- Assinaturas e declarações proíbem passagem/retorno de proprietários. Remover apenas o veto duplicaria descritores, porque o abaixamento composto copia palavras e a limpeza descartaria o dono retornado.
- Classificação de propriedade, disposição e comportamento composto estão dispersos. Parâmetros, retornos e temporários precisam distinguir cópia, transferência e empréstimo.
- Consultas de tamanho/capacidade e empréstimo dinâmico verificam estado vivo no código nativo, mas o relatório de efeitos omite a possibilidade de falha. O movimento também deve representar validação e descarte.
- A descoberta manual de chamadas omite expressões em índices dinâmicos e no acréscimo de elementos, deixando recursão sem a marca de profundidade. Novos nós não podem repetir essa lacuna.
- Temporários compostos proprietários precisam ser inicializados, consumidos e descartados sem duplicar memória. Campos de registros são aliases, não donos adicionais.
- Crescimento atual usa elementos com largura estática em palavras. Texto/bytes crescentes precisam posteriormente compartilhar alocação, reserva e descarte com passo de um byte, mantendo UTF-8 separado dos dados arbitrários.
- Não há empréstimos mutáveis, elementos proprietários em registros/listas, coleta de lixo nem tratamento recuperável geral de falhas de alocação. Nenhum desses recursos será anunciado nesta primeira entrega.

## Primeiro marco funcional escolhido

Centralizar o contrato dos valores e implementar funções proprietárias sobre as listas tipadas existentes. `mova(origem)` em expressão torna o consumo explícito; `mova(destino, origem)` histórico é preservado. Chamadas devolvem um proprietário para uma declaração nova, e retornos locais exigem movimento antes do descarte. A passagem copia somente o descritor, sem copiar os elementos.

Rejeitar consumo duplicado e mistura de empréstimo/consumo do mesmo dono numa chamada. Manter referências restritas à leitura síncrona e proibir cópia implícita, armazenamento de empréstimos e elementos com propriedade interna. Estados após movimento/liberação continuam validados nativamente.

Provar esse marco com listas vazias e grandes, inteiros/lógicos/registros, argumentos e retornos encadeados, retornos antecipados, escopos/loops, uso inválido, falha de alocação simulada, identidade da região transferida e integridade de registradores. Executar Windows e Linux de O0 a O8; adicionar biblioteca e aplicação em RS.

Texto dinâmico, bytes dinâmicos, coleções de donos, operadores lógicos e números novos permanecem marcos seguintes. Esta entrega não concluirá toda a RS 0.42A.

## Achados durante a implementação

Os testes nativos revelaram escrita indexada por ponteiro inativo quando a expressão do valor consumia a própria lista. O destino agora é verificado novamente depois do valor, preservando o índice e sem repetir efeitos.

A conta antiga da pilha omitia argumentos, temporários pendentes e o quadro principal. Além disso, a inicialização dos donos e a sondagem Windows alteravam RAX antes de salvar a conta acumulada. O contrato de chamadas passou a incluir esses custos, com verificação antes de avaliar argumentos e em todos os prólogos. O limite de 768 KiB mantém margem no PE de 1 MiB. Quadros individuais de 600.000 bytes continuam válidos; combinações que ultrapassam a conta encerram com diagnóstico.

Os callbacks de índices proprietários e emprestados também precisam transmitir os temporários da expressão envolvente. A correção foi comprovada com chamadas aninhadas e medição real do alinhamento na entrada de VirtualAlloc. A documentação do marco registra a migração para a política de pilha e a rejeição de comparação direta entre descritores proprietários.
