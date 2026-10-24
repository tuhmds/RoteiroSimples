# Escala de funcoes no emissor ELF64 escrito em RS

O emissor experimental `biblioteca_padrao/emissao_corpos_funcoes_elf.rts`
agora aceita **1 a 32 funcoes** definidas antes do bloco `inicio`,
em vez do limite anterior de 16. O limite nao se aplica ao numero de
chamadas: varias chamadas podem apontar para a mesma funcao.

## Contrato

- Ate **32 funcoes**: assinaturas existentes, retornos inteiros,
  nomes distintos e ate oito parametros por assinatura.
- **33 funcoes** ou mais: diagnostico 2, sem arquivo ELF gerado.
- Chamadas para funcoes declaradas antes ou depois da chamadora sao
  resolvidas depois da emissao do codigo.
- Recursao direta e indireta permanece proibida (diagnostico 14).
- O fechamento transitivo de dependencias em RS continua O(n^3).
  Com 32 funcoes, sao ate 32768 verificacoes da tripla de indices,
  sem recursao nem dependencia de grafo Python na compilacao realizada
  pelo emissor RS.
- Buffers locais fixos de ate 32 bytes, buffers dinamicos e
  `emprestimo[bytes]` conservam seu contrato e diagnosticos.

## Validacao

`python -m unittest testes.test_trinta_duas_funcoes_elf_rs -v`

O teste cobre cadeia de 32 chamadas diretas, declaracoes invertidas
(chamadas a funcoes anteriores), 32 funcoes com buffer fixo emprestado,
rejeicao de 33 funcoes e deteccao de ciclo indireto envolvendo 24
funcoes. Executa O0/O8 e verifica o codigo de saida de ELF nativo
em Linux; Windows compila e inspeciona o executavel gerado.

Este limite facilita programas maiores durante a transicao para
autocompilacao, mas o emissor nao gera ainda o proprio compilador.
