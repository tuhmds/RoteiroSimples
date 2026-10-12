# RS 0.40C — Contrato da representação intermediária e testes diferenciais

## Decisão de arquitetura

A RoteiroSimples continua emitindo executáveis nativos Windows x64 e
Linux x86-64, sem runtime de outra linguagem. O compilador ainda usa
Python durante a construção e, portanto, a autocompilação continua
pendente.

Não foi introduzido outro nível de otimização. A versão 0.40C busca
**reduzir a possibilidade de perda silenciosa de semântica** ao passar
da árvore sintática para a representação intermediária (IR).

A RS distingue três caminhos:

1. **Conservador:** suporta construções que a IR ainda não representa
   integralmente. Não aplica as transformações IR/SSA solicitadas por -O.
2. **Intermediário:** converte operações suportadas pela IR tipada e as
   reconstrói para a emissão nativa; pode aplicar otimizações permitidas.
3. **SSA:** para programas escalares elegíveis, aplica análises e
   alocação específicas dos níveis de otimização existentes.

O nível `-O 8` é uma **solicitação**, não uma garantia de que
todo programa seja convertido ou acelerado pelo caminho SSA.

## Cobertura de nós AST/IR

O módulo `compilador/cobertura_intermediaria.py` declara os tipos de
instruções e expressões suportados pelo conversor atual e inspeciona os
comandos encontrados, inclusive em blocos aninhados e corpos de funções.

Exemplos de comandos reconhecidos pelo caminho IR legado:
`atribua`, `texto`, `imprima_num`, `se`, `enquanto`, `para`,
`crie_lista`, `atribua_indice`, `leia_indice`, `crie_texto`,
`modifique_texto`, `limpe_texto` e `leia_texto`.

Exemplos ainda ausentes da representação intermediária:
`crie_bytes`, `adicione_byte`, `atribua_byte`,
`indice_bytes`, `carregue_de`, `grave_em`,
`publique_arquivo`, abertura e fechamento de arquivos,
operações de listas dinâmicas e algumas instruções compostas
mais recentes.

O fato de um comando **ter representação IR** não é suficiente para
tornar o programa apto a SSA. Funções, registros, escopos locais,
propriedade de recursos e outros fatores também influenciam a decisão.

## Diagnóstico público

O compilador oferece:

```text
python compilar.py meu_programa.rts --alvo linux -O 8 --mostrar-estrategia
python compilar.py meu_programa.rts --alvo windows -O 8 --mostrar-cobertura-intermediaria
```

`--mostrar-cobertura-intermediaria` apresenta as operações encontradas,
a contagem de ocorrências, lacunas de representação e o caminho
realmente escolhido.

`--mostrar-ir`, `--mostrar-efeitos`,
`--mostrar-memoria-versionada`, `--mostrar-fluxo` e demais análises
que dependam da IR **não simulam suporte a novos comandos**.
Quando o programa precisa do gerador conservador, o compilador
informa o motivo e sugere verificar a cobertura; não cria
um executável como consequência de uma análise incompatível.

A geração de código normal permanece disponível pelo conservador.
Assim, informar uma limitação de análise não significa declarar que
a própria linguagem não consegue compilar o programa.

## Segurança de transformação

`compilador/estrategia.py` consulta agora a cobertura antes de
selecionar os caminhos intermediário e SSA. Uma instrução não
representada no contrato não deve ser enviada inadvertidamente
ao conversor antigo.

`compilador/ir.py` também valida a cobertura, inclusive quando
acessado por ferramentas diretamente. Não permite descartar funções
ou registros da representação sem avisar. Em alguns casos, escopos
escalares podem ser analisados na IR porque o parser já atribuiu
identificadores internos distintos; isso **não altera** a decisão
de gerar executáveis conservadoramente para programas com escopos.

As otimizações existentes não foram reescritas nesta etapa.
O contrato verifica **cobertura de nós**, não fornece prova formal
da correção de cada transformação, de seus efeitos ou do backend SSA.
É necessário seguir com verificações independentes de equivalência.

## Ensaios

`testes/test_cobertura_intermediaria_rs040c.py` cobre:

- Operações novas recusadas no caminho IR e encaminhadas ao
  conservador, inclusive uma instrução artificial desconhecida.
- Expressões não representadas dentro de blocos aninhados.
- Reconstrução de AST compatível a partir da IR sem otimização.
- Mensagens de erro legíveis para análises indisponíveis pela CLI.
- Programas escalares em O0 a O8 com entradas pseudoaleatórias
  determinísticas e resultados conferidos matematicamente.
- Programas com `texto[N]` e `lista[N]`, além de bytes,
  verificando stdout e código de saída dos binários nativos.

A suíte preexistente também mantém testes de memória, operações
binárias e efeitos observáveis sobre arquivos nos dois sistemas.

Os testes diferenciais têm escopo limitado: entradas com sementes
fixas não substituem fuzzing estruturado, verificação formal ou
cobertura dos estados internos do compilador.

## Etapa seguinte sugerida

Antes de ampliar SSA para arquivos e listas, propor uma representação
comum de **efeitos e propriedade**: leitura/escrita de memória,
arquivos, falha recuperável, saída de processo e ciclo de vida.
Cada nova instrução deve declarar suas entradas, saídas, efeitos e
dependências para que análises e otimizações saibam o que não podem
reordenar ou eliminar.

Somente depois de testes de equivalência e da revisão do ciclo de vida
permitir progressivamente novos comandos no caminho otimizado.
Isso não exige LLVM, C, runtime estrangeiro nem alteração da
sintaxe brasileira da RS.
