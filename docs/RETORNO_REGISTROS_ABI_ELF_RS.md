# Retorno de registros: ABI ELF64 experimental (primeira etapa)

Esta etapa implementa **somente o transporte binario** do retorno de
registros inteiros no emissor escrito em RS. A sintaxe publica
`funcao criar() -> Registro { retorne registro }` **ainda nao esta
ligada a esta rotina**; o compilador de corpos continua validando
`-> inteiro`. Nao anunciar suporte completo antes de conectar chamada,
IR, tipagem e vida util.

## Contrato provisório

- O **chamador** reserva um buffer proprio para todos os slots achatados
  do tipo de registro (o layout ja e calculado em
  `esquemas_registros_elf.rts`).
- O chamador passa o endereco do **primeiro slot** como argumento oculto.
  Neste contrato ele sera empilhado por ultimo antes de `call`.
- O callee le o ponteiro oculto de `[rbp+16]` e escreve os campos
  consecutivos em `[ponteiro - indice * 8]`.
- A origem pode ser um registro local, em slots consecutivos do quadro,
  ou um parametro copiado/emprestado cujo slot armazena o ponteiro do
  primeiro campo.
- `rax` recebe o ponteiro do buffer; nao recebe um ponteiro para uma
  variavel local do callee. O chamador e o dono do armazenamento.
- O chamador deve limpar tambem o argumento oculto da pilha e deslocar
  em oito bytes a posicao dos parametros declarados do callee.
- Os valores desta etapa sao campos inteiros de 64 bits; nao ha
  transferencia de campos proprietarios dinamicos, recursao ou ABI publica.

## Implementado

`emissao_registros_elf.rts::copiar_para_retorno` gera os movs x86-64
para a transferencia. A ferramenta
`exemplos/ferramentas/testar_retorno_registros_elf_rs.rts`
usa o proprio emissor escrito em RS para produzir os dois trechos
(local e referenciado).

O teste `testes/test_retorno_registros_abi_elf_rs.py` compila a
ferramenta com O0 e O8 em Windows/Linux, verifica o formato gerado e,
no Linux x86-64, executa uma imagem ELF de prova com chamador, callee
e buffer distinto. A saida nativa deve valer 42 (= 40 + 2) em ambas
as formas de origem.

## Proxima etapa indispensavel

1. Permitir assinaturas de retorno de um tipo de registro declarado.
2. Acrescentar as representacoes tipadas de retorno e chamada na IR.
3. Implementar uso do buffer oculto na geracao do chamador,
   inclusive ajuste dos parametros e limpeza da pilha.
4. Conectar `retorne registro` e a recepcao tipada do resultado;
   conferir que nao escapam emprestimos de duracao menor.
5. Cobrir subregistros, varios parametros, chamadas encadeadas,
   retornos condicionais, recusas por tipo e O0/O8.

O helper assume que o chamador respeita os limites do esquema. A
verificacao desses limites deve ocorrer antes de chamar o helper
durante a integracao. Nenhuma alteracao no Python ou na ABI externa
e exigida por este primeiro PR.
