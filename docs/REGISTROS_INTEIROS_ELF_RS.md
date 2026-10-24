# Registros locais com campos inteiros no emissor ELF64 escrito em RS

O emissor experimental Linux x86-64 reconhece a sintaxe de registro
da RS geral, gerando layouts de slots de 64 bits na pilha.
O emissor ainda e construido pelo bootstrap Python e nao representa
autocompilacao completa.

## Exemplo

~~~rs
tipo Ponto {
    x: inteiro
    y: inteiro
}

funcao calcular() -> inteiro {
    seja p: Ponto
    p.x = 12
    p.y = -4
    retorne p.x + p.y
}
inicio {
    seja resposta = calcular()
}
~~~

Resultado: 8. Declaracoes locais sem inicializador iniciam campos
com zero. Campos nomeados podem ser escritos com registro.campo = valor
e lidos em expressoes inteiras, inclusive com chamadas e lacos.

## Contrato tecnico

- Entre 1 e 8 tipos nomeados, declarados antes das funcoes.
- Cada tipo possui de 1 a 8 campos inteiro, sem nomes duplicados.
- Cada registro local ocupa N slots de 8 bytes, sem heap.
  O nome referencia o primeiro slot; os outros sao ocultos.
- Erro 2: tipo desconhecido, declaracao malformada, campo de tipo
  diferente de inteiro ou inicializador nao suportado.
- Erro 4: definicoes ou campos duplicados.
- Erro 5: campo inexistente ou variavel fora do escopo.
- Erro 18: tentativa de usar o registro inteiro como escalar ou
  atribuir campo em objeto que nao e um registro.
- O emissor nao aceita parametros/retornos de registros, registros
  aninhados, bytes ou listas como campos, nem listas de registros.
  Essas extensoes exigem propriedade, layout e passagem mais completos.
- Limites anteriores: ate 128 slots por corpo e 32 funcoes.

## Testes

~~~sh
python -m unittest testes.test_registros_inteiros_elf_rs -v
python -m unittest discover -s testes -v
~~~

A suite exercita O0/O8, valores negativos, varias definicoes,
leitura/escrita, inicializacao, lacos, escopos e diagnosticos.
Linux executa o ELF64; Windows valida o emissor RS via bootstrap.

## Proximos passos

1. Emprestimos readonly de registros, sem copia.
2. Listas de registros com largura estatica.
3. Compilacao de unidades lexicas e nos sintaticos representados
   em RS para iniciar o bootstrap de duas geracoes.
