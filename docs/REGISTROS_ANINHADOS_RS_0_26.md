# Registros aninhados — RS 0.26

## Tipos compostos por valor

A RS aceita campos `inteiro`, `logico`, registros previamente declarados, `lista[N]` e `texto[N]`, inclusive combinações aninhadas. A declaração é resolvida estaticamente e cada campo recebe um deslocamento dentro de uma região contígua do quadro de execução.

A cópia de um registro copia **todos os seus campos**, incluindo as listas internas e os bytes de texto mais o comprimento registrado. Os campos não compartilham memória entre o original e a cópia. A linguagem continua verificando índices e capacidades no acesso aos campos.

### Exemplo

```text
tipo Endereco {
    numero: inteiro
    rua: texto[24]
}
tipo Cliente {
    endereco: Endereco
    notas: lista[3]
}
inicio {
    seja pessoa: Cliente
    pessoa.endereco.numero = 70
    copie(pessoa.endereco.rua, "Rua Mineira")
    pessoa.notas[0] = 12
    escreva(pessoa.endereco.rua)
}
```

## Resultados compostos passados diretamente

A chamada `avaliar(criar_cliente(70))` agora pode receber um registro resultante de outra função sem exigir variável intermediária na sintaxe. O compilador reserva internamente um destino temporário tipado, respeitando a ordem de avaliação dos argumentos e as convenções nativas privadas da RS.

## Restrições

- Um tipo de campo precisa ser declarado anteriormente; não há registros autorreferenciais por valor.
- A capacidade de texto e o tamanho de lista integram o tipo e precisam coincidir.
- Listas dinâmicas, alocação no heap, referências emprestadas e ponteiros públicos ainda não existem.
- A leitura de teclado dentro de funções permanece pendente.
- Programas que usam funções, registros e campos compostos usam o gerador conservador. Os níveis históricos `-O 0` a `-O 8` foram preservados; nenhum novo nível foi criado.
- Ainda se trata de compilador experimental; não utilizar em produção.

Toda a terminologia desenvolvida para esta versão usa português brasileiro. Palavras-chave da sintaxe e nomes internos novos não levam acentos. Identificadores necessários para compatibilidade com formatos externos são preservados.
