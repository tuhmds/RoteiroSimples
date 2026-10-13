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


## Biblioteca compartilhada e erros recuperaveis

A ferramenta reutiliza o modulo **biblioteca_padrao/lexico.rts**, escrito integralmente em RS, que expoe o tipo publico UnidadeLexica e as funcoes analisar e primeiro_erro. A aplicacao inicial ainda pode encerrar com codigo 2, mas **a biblioteca nunca encerra a aplicacao por erro lexico**: retorna uma lista de unidades com um diagnostico de classe negativa no final do prefixo valido.

- classe -1: caractere fora do conjunto reconhecido, com byte, linha e coluna;
- classe -2: literal textual sem aspas de fechamento, com posicao inicial;
- comprimento zero identifica o token de diagnostico; os demais tokens preservam fatias do arquivo fonte;
- primeiro_erro(empreste(unidades)) devolve o indice do diagnostico ou -1 quando nao ha erro.

Esse contrato e uma etapa intermediaria necessaria porque a RS ainda nao suporta um registro que contenha uma lista proprietaria; quando houver propriedade aninhada, a API podera evoluir para um resultado tipado completo sem mudar a semantica de erros.

A aplicacao exemplos/ferramentas/prova_lexico_recuperavel.rts demonstra que o mesmo processo pode analisar um arquivo invalido, receber o erro como dado e depois analisar outro valido. Os testes executam binarios nativos no Linux e no Windows. O trabalho tambem corrige o resolvedor de tipos importados em lista[Registro] no compilador/espacos_nomes.py, descoberto pela propria integracao.

**Limites reais:** o analisador ainda nao verifica integralmente UTF-8 malformado dentro de literais, nao normaliza Unicode e nao oferece fatias editaveis. Os offsets ficam vinculados aos bytes originais e nao sao referencias persistentes a memoria; o Studio devera manter a fonte viva enquanto interpretar suas posicoes.

## Limites e proximos passos

- Ainda nao ha argumentos de linha de comando na RS; caminho de entrada fixo.
- A ferramenta de linha de comando encerra com codigo 2, mas a biblioteca agora retorna diagnosticos recuperaveis.
- Ainda nao ha prova de paridade de todos os separadores Unicode, erros e mensagens do lexico Python.
- Nao executa analise sintatica ou semantica.
- Primeira etapa escrita em RS, e nao compilador autocompilado. A compilacao de desenvolvimento segue em Python.
- Manter a dependencia da ramificacao rs-0.42a-bytes-dinamicos. Nenhuma mesclagem automatica.
- A etapa seguinte separara a leitura de arquivo do tokenizador, representara erros tipados e implementara a arvore sintatica por indices. Depois: resolucao de nomes, tipos, IR, geracao PE/ELF e compilacao do proprio compilador, com testes diferenciais.
