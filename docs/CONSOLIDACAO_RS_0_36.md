# RS 0.36 — Consolidação do compilador orientada por aplicações

## Objetivo

Reduzir a distância entre recursos do compilador e programas que podem
ser escritos e executados sem recorrer a uma linguagem auxiliar. Nenhum
nível extra de otimização foi introduzido.

## 1. Decisão transparente do gerador

A função `compilador.estrategia.decidir_estrategia()` é a mesma decisão
usada pelo backend e pelo comando `--mostrar-estrategia`.

- O gerador **conservador** é selecionado quando o programa utiliza
  funções, registros, escopos locais, cópias compostas, listas dinâmicas
  ou operações com arquivos nativos.
- O gerador **SSA** fica disponível para programas escalares elegíveis
  quando o nível solicitado é ao menos `-O 4`.
- A **representação intermediária tipada** continua sendo utilizada
  quando o programa não necessita do gerador conservador, mas contém
  listas fixas/textos, ou usa nível `-O 0` até `-O 3`.

Quando o caminho conservador é selecionado, o nível `-O 8` pode ser
aceito pela CLI **sem aplicar transformações IR/SSA**. Isso é declarado
explicitamente e não escondido do programador.

### Comandos

```bash
python compilar.py exemplos/aplicacoes/analisar_entregas.rts --alvo linux -O 8 --mostrar-estrategia -o entregas
./entregas
```

Para Windows, altere `--alvo linux` para `--alvo windows` e use uma saída
com extensão `.exe`. Os executáveis **não dependem do Python**.

## 2. Aplicação A: cópia binária em blocos

Fonte: `exemplos/aplicacoes/copiar_arquivo_em_blocos.rts`.

- Copia os bytes de `origem.bin` para `copia.bin` no diretório de execução.
- Processa blocos de 4096 bytes e último bloco parcial, sem tentar
  carregar o arquivo inteiro para a memória.
- Suporta dados binários arbitrários, bytes NUL e arquivos vazios.
- Respeita estados de erro de `carregue_trecho` e `grave_trecho`.
- Rejeita um destino que já exista (não temos truncamento seguro).
- Depende ainda de nomes de arquivo **literais no código**. Não é um
  copiador genérico com argumentos da linha de comando.
- **Não garante cópia atômica**. Uma falha pode deixar cópia parcial.
  A checagem de existência do destino não é uma exclusão atômica
  contra processos concorrentes.

Para testar, crie `origem.bin` no diretório atual, verifique que
`copia.bin` não exista, compile e execute. Compare ambos os conteúdos
binários, não apenas seus tamanhos.

## 3. Aplicação B: análise de entregas estruturadas

Fonte: `exemplos/aplicacoes/analisar_entregas.rts`.

Prepara 150 entregas na memória, armazena cada uma como registro próprio
em uma lista dinâmica, calcula 100 entregas concluídas e soma receitas
em **centavos inteiros** (sem problemas de arredondamento de ponto
flutuante). Duas funções percorrem empréstimos imutáveis da lista,
sem copiar todo o armazenamento.

Resultado de referência: 150 entregas, 100 concluídas e 178400 centavos
de receita concluída. **Não salva os registros em um banco**; sua função
é testar o sistema de tipos e a API de coleções em uma aplicação completa.

## 4. Critérios automatizados

O arquivo `testes/test_consolidacao_rs036.py` compila e executa os mesmos
programas com cada nível de otimização `-O 0` até `-O 8`, no Windows e
Linux x86-64. Verifica:

- Aritmética, condições e laços em um programa escalar.
- Listas fixas, índices e acesso a memória.
- Registros, funções, listas dinâmicas e empréstimos de leitura.
- Cópia de diferentes arquivos binários, incluindo dados aleatórios,
  zeros, UTF-8 arbitrário, arquivo vazio e fronteira de bloco.
- Preservação exata dos bytes, com comparação independente em Python
  **no ambiente de teste**, nunca dentro do executável RS.
- Destino já existente não deve ser substituído ou corrompido.
- Origem ausente precisa ser diagnosticada.
- O diagnóstico deve distinguir backend SSA de gerador conservador.

**Critério de aceite:** todas essas verificações passam em ambos
os sistemas. Isso é uma matriz de regressão — não constitui prova
formal de equivalência para todos os programas possíveis.

## 5. Lacunas tornadas visíveis pelas aplicações

Ainda faltam: caminhos recebidos por argumentos/variáveis, tipo
`byte` e dados binários tipados, truncamento seguro, gravação atômica,
sincronização durável, cancelamento, interface com bibliotecas externas,
documentação de garantias da ABI e testes de concorrência/interrupção.

O motor Dados RS permanece projeto separado. Essas aplicações são
instrumentos para encontrar e priorizar lacunas antes de escrevê-lo.
