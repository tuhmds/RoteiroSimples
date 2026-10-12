# RS 0.37 — Dados binários tipados e encerramento explícito

## Objetivo

Separar dados binários de texto, aplicar limites verificáveis em cada
operação e permitir que programas comuniquem sucesso ou falha ao sistema.
Não é um banco de dados nem uma implementação completa de acesso a
arquivos durável.

## Tipo bytes[N]

```text
inicio {
    seja dados: bytes[4]
    adicione_byte(dados, 0)
    adicione_byte(dados, 255)
    dados[0] = 82
    escreva(dados[1])
    escreva(tamanho(dados))
    escreva(capacidade(dados))
}
```

`bytes[N]` é um valor **diferente** de `texto[N]`. Sua capacidade é
fixada na declaração e seu comprimento começa em zero. Cada chamada
`adicione_byte` acrescenta exatamente um byte, exigindo que ainda haja
espaço. `dados[indice]` lê somente posições anteriores ao comprimento
atual; `dados[indice] = valor` **substitui** um byte existente e não
estende o buffer. `limpe(dados)` redefine seu comprimento para zero;
não substitui uma operação de limpeza de memória secreta. O conteúdo
anterior permanece inacessível por índice RS válido até ser substituído.

O valor numérico dos bytes deve estar entre 0 e 255, inclusive; valores
fora da faixa, posições negativas, leituras após o comprimento e
tentativas de ultrapassar a capacidade encerram o processo com
diagnóstico e código de erro diferente de zero. **Não há conversão
silenciosa que descarte bits.**

A representação de armazenamento contém comprimento em 64 bits e bytes
contíguos. Nenhuma leitura por índice pode ultrapassar os dados
efetivamente inicializados. O tipo é copiável por valor (inclusive em
registros e parâmetros), sem confusão com `texto[N]`.

## Acesso a arquivos

`grave_trecho("arquivo", bytes, posicao, estado)` e
`carregue_trecho("arquivo", bytes, posicao, quantidade, estado)`
aceitam `bytes[N]` além do `texto[N]` legado. Dados são
transferidos sem UTF-8 implícito. Na leitura, o comprimento passa a ser
o total efetivamente lido; erro invalida o comprimento do destino.
Os códigos recuperáveis dessas operações continuam -1 a -4.

Os comandos que tratam especificamente de texto (como
`escreva(buffer)`, `copie` e `junte`) **não** aceitam `bytes[N]`.
Isso impede exibir binários arbitrários involuntariamente como texto.

## Encerramento do programa

`encerre(codigo)` termina imediatamente a execução e devolve ao
sistema um código inteiro entre 0 e 255. `0` indica sucesso por
convenção; valores diferentes de zero indicam falhas definidas pela
aplicação. O compilador verifica o tipo e, durante a execução, a faixa
permitida. Um valor fora de 0..255 gera diagnóstico e saída com erro.

O encerramento é imediato; não substitui tratamento de erros,
finalização explícita de transações nem limpeza de recursos da aplicação
antes de sair. O sistema operacional libera os recursos do processo, mas
**não garante sincronização de arquivos nem desfaz escritas parciais**.

## Exemplo de integração

`exemplos/aplicacoes/criar_cabecalho_binario.rts` constrói um pequeno
cabeçalho didático com assinatura, versão e contador de registros,
escreve os bytes e os recupera para validação. É um teste real de
serialização e leitura com comprovante de saída de processo.
**O cabeçalho não define o formato do Dados RS.**

## Testes de segurança

- Valores limítrofes 0/255, -1/256 e comprimentos além da capacidade.
- Índices fora da região escrita, negativos e enormes.
- Cópias de buffers, campos de registros e parâmetros por valor.
- Leitura e escrita de bytes 0x00, 0xFF e dados não UTF-8.
- Conteúdo binário gerado por semente fixa e comparado em bytes.
- Mesma execução com `-O 0` a `-O 8` em Windows e Linux.
- Status de saída 0, 1, 127, 255 e valores inválidos.
- Rejeição estática de usos indevidos como texto.

A suíte valida cenários reais, **não é prova matemática de ausência de
erros**. A linguagem ainda precisa de byte dinâmico, arquivos com
identificadores proprietários, escrita durável, travamento e atualização
atômica antes de construir um banco confiável.
