# Dados RS — Prova executavel de arquivo binario versionado

**Situacao:** ensaio de integracao da linguagem, nao motor transacional. O Dados RS completo tera repositorio separado, conforme CONTRATO_DADOS_RS.md.

## Prova minima entregue

Dois programas escritos inteiramente em RS, disponiveis em exemplos/dados_rs:

- prova_gravar.rts cria o arquivo entregas.rsd no diretorio atual contendo 100 registros.
- prova_ler.rts abre o arquivo em processo independente, valida inteiramente seu tamanho, assinatura, versao, contagem, IDs sequenciais e valores, e soma os campos.
- Um teste diferencial Python verifica a serializacao byte a byte e exercita truncamento, excesso de conteudo, corrupcao de cabecalho e registros.

## Formato inicial apenas demonstrativo

- Cabecalho de 16 bytes.
- Assinatura ASCII RSDB (4 bytes).
- Versao 1 (4 bytes, ordem pouco significativa).
- Quantidade 100 (8 bytes, ordem pouco significativa).
- Cem registros de 16 bytes: codigo sem sinal de 64 bits e valor sem sinal de 64 bits, tambem em ordem pouco significativa.
- Tamanho total de 1616 bytes.

O leitor valida primeiro o comprimento exato antes de indexar, recusa sinal de valor invalido antes de compor um numero assinado, e devolve codigo de saida 3 para rejeicao.

## Executar a prova

Na raiz do repositorio, compilar os dois programas:

    python compilar.py exemplos/dados_rs/prova_gravar.rts --alvo linux -O 0 -o gravador
    python compilar.py exemplos/dados_rs/prova_ler.rts --alvo linux -O 0 -o leitor

Executar ambos na mesma pasta de testes, na ordem gravador e leitor. Para Windows, ajustar --alvo windows e extensao .exe.

Testar em Windows e Linux:

    python -m unittest testes.test_dados_rs_prova_binaria -v
    python -m unittest discover -s testes -v

## Limites e expansao

- O arquivo e uma demonstracao de serializacao, nao um formato definitivo; versoes futuras ainda nao estao congeladas.
- A gravacao atual usa grave_arquivo, que nao oferece transacao nem garantia de integridade apos falha parcial de gravacao.
- Nao existem paginas, esquemas dinamicos, consultas, indices, WAL, isolamento nem transacoes ACID.
- Nomes de arquivo ainda sao literais e nao ha sistema de parametros de processo.
- Proximos passos: biblioteca de serializacao e desserializacao com erros recuperaveis, registros com tipos dinamicos, arquitetura de paginas, IDs estaveis, diario, validacao de concorrencia e migracao a repositorio exclusivo.
- A prova depende da RS 0.42A.3 e sera revisada independentemente, sem mesclagem automatica.
