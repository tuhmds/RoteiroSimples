# RS 0.35 — Acesso binário posicional com erros recuperáveis

## Por que desenvolver

O Dados RS precisará consultar páginas sem carregar um banco inteiro na
memória, alterar partes de um arquivo sem truncá-lo, distinguir EOF de
falha e continuar executando quando um arquivo não existir. A RS 0.34 não
permitia isso: gravava ou carregava arquivos completos e encerrava o
programa em falhas de arquivo.

Esta etapa adiciona duas primitivas síncronas para acesso binário
posicional, com deslocamentos de **inteiro de 64 bits**:

```text
inicio {
    seja bytes: texto[100]
    seja estado = 0

    copie(bytes, "pagina01")
    grave_trecho("banco.rsd", bytes, 4096, estado)
    se estado < 0 {
        escreva(estado)
    }

    carregue_trecho("banco.rsd", bytes, 4096, 8, estado)
    se estado >= 0 {
        escreva(bytes)
    }
}
```

## Contrato público

- `grave_trecho("arquivo", buffer, posicao, estado)` usa exatamente o
  comprimento de `buffer: texto[N]` e grava na posição indicada.
  Cria o arquivo se ele não existir, **sem truncar** arquivos existentes.
- `carregue_trecho("arquivo", buffer, posicao, quantidade, estado)`
  lê até `quantidade` bytes na posição dada. A quantidade deve ser não
  negativa e não pode ultrapassar a capacidade de `buffer`.
- `estado: inteiro` recebe o número de bytes processados quando a operação
  é bem-sucedida. **Zero** significa nenhuma transferência (arquivo vazio,
  posição depois do fim, leitura de zero bytes ou gravação de buffer vazio).
- Se `estado` for negativo, a falha é recuperável:
  - `-1`: falha ao abrir/criar;
  - `-2`: falha durante leitura ou escrita;
  - `-3`: posição, quantidade ou posicionamento inválidos;
  - `-4`: falha no fechamento.
- Na leitura, o comprimento do `buffer` passa a ser exatamente o total
  lido, inclusive zero. Em caso de erro, o comprimento passa a zero,
  mas **não há garantia de preservar bytes anteriores**.

O acesso é em bytes, não interpreta UTF-8, admite zeros e dados binários
arbitrários. `texto[N]` é um armazenamento provisório de bytes: ainda
faltam `bytes[N]` ou `sequencia[byte]` como tipos próprios da linguagem.

## Implementação

- Linux x86-64: `openat`, `pread64`, `pwrite64`, `close`
  (com repetição de `EINTR` nas transferências).
- Windows x64: `CreateFileA`, `SetFilePointerEx`, `ReadFile`,
  `WriteFile` e `CloseHandle`.
- Leitura/escrita parciais são repetidas; leituras param no fim do arquivo.
- O arquivo é aberto e fechado a cada comando.
- Comprimentos maiores que a capacidade de destino e soma
  `posicao + quantidade` fora do intervalo de inteiro assinado são rejeitados
  antes de abrir o arquivo.
- Nomes de arquivo são literais ASCII relativos, como na RS 0.34.
- Não se grava um marcador de fim de texto nem se acrescenta uma quebra
  de linha. O número exato de bytes fica no próprio valor `estado`.

## Garantias que ainda NÃO temos

**Nenhuma gravação desta etapa é transacional, atômica ou durável após queda
de energia.** Um erro depois de escrita parcial deixa dados parciais no
arquivo e devolve um código negativo, sem reverter alterações. O comando
não executa `fsync`/`FlushFileBuffers`, não gerencia travas e não é
apropriado para uso concorrente sem coordenação externa.

A etapa seguinte deve introduzir identificadores de arquivo, fechamento
seguro, sincronização no disco, substituição atômica e estruturas de erro
tipadas. Não confundir essas primitivas com um motor de banco de dados.
