# Fatias de bytes e validacao UTF-8 em RoteiroSimples

Esta etapa implementa uma biblioteca fundamental **escrita em RS**, que
trabalha diretamente sobre `bytes` por emprestimo, sem copiar o conteudo
para acessar ou comparar intervalos.

## Modulo `biblioteca_padrao/fatias_bytes.rts`

O tipo `FatiaBytes` guarda apenas `deslocamento` e `comprimento`, mais um
codigo de erro recuperavel. A fonte continua sob posse do chamador.

- `contida(total, inicio, comprimento)`: verifica limites sem calcular
  `inicio + comprimento` antes das verificacoes; rejeita negativos.
- `recortar(fonte, inicio, comprimento)`: gera fatia, inclusive vazia no
  fim do buffer.
- `subfatia(fonte, origem, inicio, comprimento)`: deriva um intervalo
  relativo a uma fatia valida.
- `ler(fonte, fatia, indice)`: retorna `ResultadoByte`, em vez de ler
  fora dos limites ou encerrar o processo.
- `iguais(fonte_a, a, fonte_b, b)`: compara fatias binarias sem
  alocacoes intermediarias, incluindo byte zero e valores 128 a 255.
- `validar_utf8(fonte)`: verifica UTF-8 estrito e retorna posicao e
  codigo recuperavel.

Erros do UTF-8: **1** byte inicial invalido, **2** truncado,
**3** byte de continuacao invalido, **4** codificacao alongada,
**5** substituto UTF-16, **6** ponto acima de U+10FFFF.

## Integracao no compilador

O analisador `lexico.rts` utiliza a biblioteca para validar o arquivo
antes da separacao em tokens. Um arquivo com UTF-8 malformado produz
token diagnostico de classe **-3**, com indice do byte, linha e coluna
(considerando CRLF e colunas por ponto de codigo).

O emissor `emissao_fluxo_elf.rts` usa fatias verificadas para
comparar nomes e verifica limites nas comparacoes com texto e simbolos.
A ferramenta lexical demonstra uma mensagem propria para UTF-8 invalido.

Esse endurecimento impede um texto malformado entre aspas de passar
silenciosamente pela analise lexical. A biblioteca nao transforma nem
normaliza Unicode; identidades como nomes acentuados permanecem
sujeitas as regras existentes da linguagem.

## Testes

- `testes/test_fatias_bytes_rs.py` compila uma ferramenta escrita em RS
  para Windows/Linux (O0 e O8), usa arquivos binarios reais, confronta
  as fatias com oraculo Python e cobre todas as seis classes de erro
  UTF-8.
- `testes/test_lexico_nativo_rs042c.py` exercita arquivos com bytes
  UTF-8 invalidos e diagnosticos de linha e coluna.
- As suites existentes do compilador RS e dos emissores ELF servem de
  verificacao de regressao da nova dependencia.

## Limites atuais

As fatias sao offsets, nao ponteiros ou visoes com garantia de vida
automatizada: a fonte deve sobreviver a cada uso, e as funcoes recebem
um emprestimo valido explicitamente. Isso **nao** adiciona ainda
variaveis `bytes` nem `lista` ao subconjunto ELF inteiro, nem
conclui a autocompilacao do compilador. O bootstrap Python permanece.
