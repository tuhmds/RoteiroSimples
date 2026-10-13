# RS 0.42C — Primeiro analisador lexico escrito em RS

**Estado:** marco experimental para revisao, dependente das PRs #2, #3 e #4. Nao e um compilador completo nem substitui o analisador Python.

## Objetivo comprovavel

O arquivo de exemplo exemplos/ferramentas/analisador_lexico_rs042c.rts usa somente construcoes RS:

1. Abre o arquivo local codigo_fonte.rts como bytes dinamicos.
2. Percorre os bytes, reconhece comentarios de duas barras, espacos, identificadores ASCII, numeros, textos UTF-8 e operadores/simbolos.
3. Guarda cada unidade lexica em lista dinamica de registros contendo classe, inicio e comprimento em bytes, linha e coluna.
4. Imprime a contagem e os campos numericos, para reconstruir a fatia original.
5. Encerra com codigo 2 nos caracteres invalidos fora de textos e textos sem fechamento.

Os tokens **nao possuem copia textual de cada valor**. Guardam posicoes no arquivo original. Isso evita guardar proprietarios dinamicos dentro de registros, recurso ainda pendente, e fornece estruturas aproveitaveis pelo Studio, parser e biblioteca de diagnosticos.

## Executar

Na raiz do repositorio, compilar com:

    python compilar.py exemplos/ferramentas/analisador_lexico_rs042c.rts --alvo linux -O 0 -o analisador

Em Windows, mudar o alvo para windows e a saida para analisador.exe. Colocar o arquivo codigo_fonte.rts no diretorio em que executar o binario.

Formato de saida: primeiro a quantidade de unidades. Depois, por unidade, cinco inteiros em linhas independentes: classe, inicio_byte, comprimento_byte, linha e coluna.
Classes: 1 identificador, 2 numero, 3 texto, 4 simbolo, 5 operador duplo.

## Testes diferenciais

    python -m unittest testes.test_lexico_nativo_rs042c -v
    python -m unittest discover -s testes -v

O teste usa compilador/lexico.py como referencia. Valida classes, posicoes, comprimentos e slices exatos em UTF-8 para programas, funcoes, operadores, comentarios, CRLF, Unicode em literais, vazio e falhas selecionadas.

## Limites e proximos passos

- Ainda nao ha argumentos de linha de comando na RS; caminho de entrada fixo.
- Falhas lexicas encerram o processo; na versao seguinte devem retornar resultados recuperaveis.
- Ainda nao ha prova de paridade de todos os separadores Unicode, erros e mensagens do lexico Python.
- Nao executa analise sintatica ou semantica.
- Primeira etapa escrita em RS, e nao compilador autocompilado. A compilacao de desenvolvimento segue em Python.
- Manter a dependencia da ramificacao rs-0.42a-bytes-dinamicos. Nenhuma mesclagem automatica.
- A etapa seguinte separara a leitura de arquivo do tokenizador, representara erros tipados e implementara a arvore sintatica por indices. Depois: resolucao de nomes, tipos, IR, geracao PE/ELF e compilacao do proprio compilador, com testes diferenciais.
