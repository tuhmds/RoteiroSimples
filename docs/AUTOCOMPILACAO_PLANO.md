# Autocompilacao da RS

A partir desta etapa, a autocompilacao passa a orientar as prioridades. O compilador Python permanece como referencia e bootstrap, nao como destino da evolucao.

## Marcos de aceite

1. Uma biblioteca de analise de expressoes escrita em RS, com testes nativos Windows/Linux.
2. Um analisador de declaracoes e blocos em RS sobre os tokens existentes.
3. Resolucao de nomes e tipos de um subconjunto fechado.
4. Emissao ELF x86-64 simples em RS e validacao diferencial.
5. Reconstrucao do compilador por ele mesmo e comparacao dos artefatos.
6. Emissao PE x86-64 e evolucao das otimizacoes em RS.

A cada marco, manter regressao nativa, equivalencia de erros e medicao de memoria. Nao declarar bootstrap concluido antes de um ciclo real de autocompilacao reproduzivel.

## Prioridades e limites

Suspender novas otimizacoes do compilador Python, salvo correcoes de seguranca, conformidade e bloqueadores da transicao. Nao excluir o backend antigo; usa-lo como oraculo de referencia. A primeira cadeia autocontida pode suportar apenas um subconjunto da sintaxe, desde que seja suficiente para compilar seu proprio codigo.
