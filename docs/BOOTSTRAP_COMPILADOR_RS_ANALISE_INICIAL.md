# Autocompilacao — analisadores iniciais escritos em RS

**Estado:** implementacao experimental, ainda nao e um compilador autonomo.

O objetivo destas entregas e migrar gradualmente a cadeia de compilacao
para codigo RS sem modificar a semantica do compilador Python de referencia.
Os executaveis destes modulos sao produzidos pela cadeia atual de bootstrap.

## Componentes

- `padrao/lexico.rts`: unidades lexicas e posicoes da fonte (preexistente).
- `padrao/estrutura_compilador.rts`: pares de delimitadores e erros recuperaveis (#37).
- `padrao/expressoes_compilador.rts`: arvore de expressoes aritmeticas por indices,
  com literais, nomes, operadores unarios e binarios, parenteses e precedencia (#38).
- `padrao/assinaturas_compilador.rts`: assinaturas de funcoes com intervalos
  de tipos, parametros e corpos, sem resolver nomes nem tipos (#39).
- `padrao/declaracoes_compilador.rts`: identifica comandos `seja`, seus
  intervalos de tipo e inicializador; aceita delimitadores e quebra de linha (#40).

## Contratos e limites importantes

Os indices dos nos sao relativos a lista de nos produzida na analise;
as unidades referenciam a fonte original sem copiar cada identificador.
Esta estrutura permite percorrer arvores sem tipos recursivos nem ponteiros
brutos. Os analisadores ainda sao **independentes**: a unificacao posterior
precisara estabelecer um formato comum para declaracoes, expressoes, blocos,
funcoes e seus escopos.

Nenhum destes modulos valida a existencia de tipos, resolve nomes, cria IR,
gera ELF/PE ou executa um ciclo de autocompilacao. A biblioteca de expressoes
reconhece somente `+ - * / %`, sinais unarios e parenteses, alem de literais
inteiros e identificadores; chamadas, comparacoes, logicos, membros,
indices, textos e resultados devem ser incorporados por etapas.

O reconhecedor de assinaturas captura a **estrutura** de funcoes e seus
tipos sintaticos; nao verifica regras de declaracao de funcao, assinaturas
duplicadas, contratos de retorno ou chamada. O reconhecedor de `seja`
trabalha com instrucoes por linha ou separadas por `;`, respeitando
parenteses e colchetes; tambem nao verifica a expressao inicializadora.

Nao usar nenhum destes modulos como validador completo de codigo RS.

## Verificacao

Na raiz do repositorio, executar:

```text
python -m unittest testes.test_estrutura_compilador_rs testes.test_expressoes_compilador_rs testes.test_assinaturas_compilador_rs testes.test_declaracoes_compilador_rs -v
```

Os testes geram executaveis para Windows e Linux, executam o alvo nativo
nos niveis O0 e O8 e conferem retornos e diagnosticos. Para validar a
versao integrada, exigir a CI completa em Windows/Linux e Python 3.10,
3.11 e 3.14.

## Passos seguintes

1. Unificar AST de expressoes com funcoes, declaracoes e blocos.
2. Completar expressoes: chamadas, acesso a campos e colecoes, comparacoes
   e logicos com precedencia e diagnosticos coerentes.
3. Implementar tabelas de simbolos, escopos e analise de tipos/propriedade.
4. Produzir IR nativa inicial e gerar um subconjunto ELF x86-64 em RS.
5. Comparar binarios e comportamento com o compilador de referencia.
6. Executar dois ou mais ciclos de reconstrucao do proprio compilador,
   preservando testes independentes antes de anunciar autocompilacao.
