# RS 0.42T — Textos e coleções para aplicações

## Entrega da linguagem

`lista[texto]` possui diretamente textos dinâmicos, sem exigir um registro
envoltório escrito pelo usuário. Campos de registros, parâmetros, retornos
e empréstimos de listas aceitam esse elemento. `resultado[lista[T]]` usa a
especialização existente para as listas dinâmicas de elementos admitidos
pelo parser, incluindo texto, inteiros, lógicos e registros suportados.
Isso não habilita listas arbitrariamente aninhadas ou resultados recursivos.

A [referência consolidada](LINGUAGEM_RS.md) reúne sintaxe, tipos, propriedade,
erros e limites. A especificação da 0.9 permanece como documento histórico.
Não houve migração do compilador para outra linguagem nesta entrega.

```text
funcao criar() -> texto {
    seja valor: texto = "Ação 🌱"
    retorne mova(valor)
}
funcao consultar(valor: emprestimo[texto]) -> inteiro {
    retorne caracteres(valor)
}
inicio {
    seja nomes: lista[texto]
    adicione(nomes, criar())
    escreva(consultar(empreste(nomes[0])))
    seja retirado: texto = retire(nomes, 0)
    escreva(retirado)
}
```

## Propriedade e armazenamento

Cada elemento tem dono único. `adicione` e substituição por índice exigem
`mova(texto)` ou um produtor novo; o elemento anterior da substituição é
descartado. `retire` remove e transfere um texto para declaração, argumento
ou retorno. `remova_ultimo`, `limpe_lista`, liberação e saída de escopo
descartam os textos atingidos exatamente como nas coleções de registros.
O crescimento move os descritores e preserva os endereços dos conteúdos.

`empreste(nomes[indice])` é somente leitura durante a chamada. Pode ser
obtido também de `emprestimo[lista[texto]]`; não pode escapar para variável,
retorno ou campo. Índice e vida do descritor são verificados. A mesma árvore
de chamada não pode consumir a lista e emprestar seu elemento, ou retirar
um elemento enquanto outro argumento empresta/consome a lista.

O descritor de texto mantém as três palavras e a ABI existentes. A lista
usa 24 bytes por elemento no heap crescente; a pilha usa a orientação
decrescente anterior. Uma reserva de três palavras adapta a vista para
empréstimo, sem possuir ou copiar os bytes do texto. Reservas entram no
tamanho efetivo do quadro e no orçamento de pilha. Os auxiliares de descarte
por tipo reutilizam o percurso de folhas proprietárias existente; textos
não recebem um segundo alocador ou um registro artificial.

## Biblioteca escrita em RS

`padrao/textos.rts` mantém `duplicar`, `concatenar` e `vazio` e acrescenta:

| Operação | Retorno e semântica |
| --- | --- |
| `encontrar(origem, procurado)` | `resultado[inteiro]`; primeira posição em caracteres, -1 ausente; padrão vazio na posição 0 |
| `recortar(origem, posicao_inicial, quantidade)` | `resultado[texto]`; recorta caracteres completos; admite quantidade zero no fim |
| `separar(origem, separador)` | `resultado[lista[texto]]`; separação literal, não sobreposta; preserva partes vazias nas extremidades e entre separadores |
| `juntar(partes, separador)` | `resultado[texto]`; lista vazia produz texto vazio; separador vazio é aceito |

As entradas são empréstimos. Valores escalares Unicode são as unidades de
posição: emoji simples conta como um, acento combinante conta separado,
sequências de grafemas não são agrupadas e não há normalização implícita.
Tamanhos em bytes continuam disponíveis separadamente. NUL faz parte do
conteúdo e não é terminador para essas operações.

As funções retornam falhas recuperáveis: código 1 propagado da conversão
UTF-8, 2 para posição inicial inválida, 3 para quantidade inválida e 4 para
separador vazio em `separar`. Entradas externas devem ser lidas como bytes
e decodificadas explicitamente por `padrao/utf8.rts`; o carregamento direto
de texto conserva a falha fatal anterior se o arquivo for inválido. OOM,
índice inválido e uso após movimento não se tornam capturas de `resultado`.

Os algoritmos validam e copiam UTF-8 explicitamente. `recortar` não soma
posição e quantidade sem limites; intervalos enormes são recusados ao
atingir o fim da entrada. Busca e separação percorrem pontos válidos e
comparam bytes literais, sem cortar uma sequência UTF-8. A busca ingênua
pode custar O(N*M); não há promessa de busca linear geral. A biblioteca
atual aloca cópias intermediárias e as funções importadas podem ser emitidas
mesmo quando não são chamadas: tamanho e custo podem crescer com o módulo.

## Aplicação e reprodução

O [leitor de configuração](../exemplos/ferramentas/ler_configuracao_rs042t.rts)
recebe `configuracao.txt` em UTF-8. Aceita linhas `chave=valor`, comentários
de linha `#`, linhas vazias e espaços ASCII/tab/CR nas extremidades.
Imprime cada chave e valor em linhas separadas. Valores vazios são aceitos;
chaves vazias ou ausência de `=` produzem diagnóstico de linha e código 5.
O primeiro `=` separa os campos; os seguintes pertencem ao valor. Não há
interpretação especial de aspas, escapes, seções ou chaves duplicadas.
Uma entrada inválida encerra com status 2; resultados anteriores podem ter
sido impressos. Falhas posteriores à consulta do arquivo conservam as
regras nativas de E/S, sem promessa de leitura atômica ou captura geral.

```text
python compilar.py exemplos/ferramentas/ler_configuracao_rs042t.rts -O 8 -o configuracao.exe
python -m unittest testes.test_textos_colecoes_rs042t testes.test_abi_lista_textos_rs042t -v
python -m benchmarks.medir --fonte benchmarks/textos_rs042t.rts --repeticoes 17 --json textos.json
```

Use `--alvo linux` e nome sem `.exe` para ELF. O benchmark executa 200
separações/junções, deve imprimir `1000`, e confere saídas e arquivos nos
nove níveis. O tempo medido inclui inicialização do processo; selecionar
SSA em funções auxiliares não garante aceleração do programa completo.

## Ensaios

Testes nativos confrontam crescimento, substituição, retirada, descarte,
campos, listas emprestadas, retornos/resultados e conflitos de alias.
Oráculos Python usam `str.split`, `str.find`, fatias e contagens Unicode
independentes, com sementes fixas, caracteres combinantes, emoji, NUL e
vazios. São 16 casos de separação/junção e 16 de busca/recorte em O0–O8.
O leitor de configuração é exercitado com LF, CRLF, falha sintática, arquivo
ausente e UTF-8 inválido.

Ensaios Windows isolados verificam 27 alocações/27 liberações, identidade dos
conteúdos após crescimento, oito registradores inteiros, dez vetoriais e RSP.
`RtlVirtualUnwind` e INT3 reais conferem os auxiliares especializados de texto.
Linux executa os mesmos programas funcionais e oráculos em sua CI nativa.
Não há declaração de prova completa de segurança de memória.
