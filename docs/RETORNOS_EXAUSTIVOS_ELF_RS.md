# Análise de retorno exaustivo no emissor ELF escrito em RS

O analisador de instruções `biblioteca_padrao/instrucoes_integradas_elf.rts`
verifica, dentro do subconjunto experimental de funções com retorno
`inteiro`, quando todos os caminhos de uma função terminam em `retorne`.

## Comportamento novo

```rs
funcao escolha(n: inteiro) -> inteiro {
    se n > 0 {
        retorne 31
    } senao {
        retorne 43
    }
}
inicio {
    seja resultado = escolha(5)
}
```

O exemplo dispensa o retorno incondicional ao fim da função, pois ambos
os ramos retornam. A IR escrita em RS usa a categoria 8 para a transição
`senao`, categorias 3 e 4 para `se` e `enquanto`, categoria 5 para o
fechamento e categoria 7 para `retorne`. A verificação percorre a IR
e mantém uma pilha de escopos, com a garantia de retorno por ramo.

- `retorne` garante término do caminho no bloco correspondente.
- `se` sem `senao` não garante retorno, independentemente do ramo verdadeiro.
- `se ... senao` garante retorno apenas quando **ambos** os ramos garantem.
- `enquanto` não garante retorno: sua condição pode ser falsa na primeira avaliação.
- Instruções após uma estrutura que garantiu retorno são recusadas com
  **erro 10** e índice do primeiro token inalcançável.
- Uma função com caminho sem retorno continua recusada com **erro 11**.

O exame é conservador, estrutural e não executa expressões constantes,
não assume que um laço executará e não usa análise simbólica. O emissor
permanece restrito a chamadas e parâmetros `inteiro`, sem recursão de
funções alvo. A cadeia de bootstrap **ainda usa Python**: este marco
não representa autocompilação integral.

## Verificação

```sh
python -m unittest testes.test_emissao_corpos_funcoes_elf_rs -v
python -m unittest discover -s testes -v
```

Os testes O0/O8 cobrem os dois ramos, condições aninhadas, chamadas,
código inalcançável, `se` parcial e laços, além das regressões anteriores.
Executáveis ELF gerados são executados quando o teste roda em Linux x86-64;
o Windows hospeda o emissor compilado, sem executar ELF Linux.
