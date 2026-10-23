# Subconjunto ELF64 escrito em RS: `se ... senao`

## Motivação
O emissor experimental `biblioteca_padrao/emissao_corpos_funcoes_elf.rts`,
implementado na própria RoteiroSimples, agora aceita `senao` em condições
do bloco `inicio` e dos corpos de funções inteiras.

Exemplo de programa-fonte admitido pelo emissor experimental:

```rs
funcao escolher(n: inteiro) -> inteiro {
    seja resultado = 0
    se n > 0 {
        resultado = 17
    } senao {
        resultado = 9
    }
    retorne resultado
}
inicio {
    seja r = escolher(-3)
}
```

## Implementação
- A representação intermediária de instruções usa a categoria **8**
  para a transição entre os dois ramos. A pilha de controles verifica
  qual `se` está aberto, rejeita `senao` em `enquanto`, o segundo
  `senao` e a ausência de `{`.
- A emissão x86-64 preserva o desvio condicional que entra no ramo
  falso, acrescenta um `jmp rel32` ao fim do ramo verdadeiro e
  corrige o salto final no fechamento da estrutura. Estruturas
  aninhadas não compartilham deslocamentos.
- A análise de retornos mantém a regra conservadora anterior:
  funções precisam de um `retorne` final incondicional no nível
  externo, mesmo que os dois ramos já retornem.
- O tratamento limita-se ao emissor **de corpos com funções**;
  não amplia os demais emissores ELF mais simples.

## Testes
```sh
python -m unittest testes.test_emissao_corpos_funcoes_elf_rs -v
python -m unittest discover -s testes -v
```
Ensaios O0/O8: ramos verdadeiro e falso, retornos antecipados,
aninhamento, `senao` dentro de `enquanto`, chamadas nos predicados,
`senao` indevido e formatos inválidos. Em Linux x86-64, os testes
executam o ELF gerado. Windows compila a ferramenta RS nativa que
gera ELF Linux, conferindo seus bytes e seus diagnósticos.

## Limitações
É um **passo de autocompilação**, não autocompilação concluída.
Ainda se usa `compilar.py` (compilador de bootstrap escrito em
Python) para construir o executável emissor escrito em RS.
O alvo desse emissor é ELF64 Linux; Windows é hospedagem de testes,
não um novo alvo de saída deste módulo. Não há recursão na linguagem
alvo deste subconjunto e as assinaturas continuam restritas a inteiros.
