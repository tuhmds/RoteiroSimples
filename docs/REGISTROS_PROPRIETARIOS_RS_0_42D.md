# RS 0.42D — Propriedade em campos de registros locais

**Estado:** primeiro marco de implementacao, com testes nativos Windows/Linux. Nao equivale ao suporte completo a registros proprietarios como valores transferiveis.

## Funcionalidades implementadas

Os campos de registros podem ser `texto`, `bytes`, `lista[inteiro]` ou `lista[logico]` dinamicos, alem dos campos fixos e registros ja disponiveis. Um registro pode conter outro registro com campos proprietarios.

Exemplo:

```text
tipo Documento {
    titulo: texto
    corpo: bytes
    paginas: lista[inteiro]
}
inicio {
    seja documento: Documento
    copie(documento.titulo, "Exemplo")
    adicione_byte(documento.corpo, 65)
    adicione(documento.paginas, 2)
    seja destino: bytes
    mova(destino, documento.corpo)
    mova(documento.corpo, destino)
    escreva(documento.titulo)
}
```

O analisador registra cada campo como uma vista do mesmo quadro de pilha do registro. O layout continua centralizado em `compilador/disposicao_tipos.py`, sem descricao alternativa de tamanho. A declaracao de registro zera sua representacao. Os campos dinamicos participam de limpeza automatica por escopo e encerramento de funcao, incluindo uso dos caminhos historicos de retorno e lacos. `mova` aceita caminhos pontuados de campos, preserva dono unico e inativa a origem ate eventual transferencia de volta.

## Bloqueios deliberados de seguranca

O compilador **rejeita estaticamente**:
- copia por inicializacao/atribuicao de registro que contenha proprietario;
- atribuicao implicita de campo proprietario;
- parametro ou retorno por valor de registro proprietario;
- lista de registros proprietarios, enquanto nao houver transferencia segura para elementos.

O gerador conservador permanece responsavel por esse recurso mesmo quando o programa solicita `-O8`. Nao foram introduzidos `malloc`, LLVM, C, JavaScript ou runtime externo obrigatorio no executavel.

## Verificacao

```text
python -m unittest testes.test_registros_proprietarios_rs042d -v
python -m unittest discover -s testes -v
python compilar.py exemplos/aplicacoes/registro_com_proprietarios_rs042d.rts --alvo linux -O 8 -o registro
```

Para Windows, trocar o alvo e gerar `registro.exe`. Testes positivos com arquivo real exercitam texto UTF-8, bytes, lista, movimentacao, retorno de uso, bloco local e resultado em `-O0` e `-O8`. Testes negativos provam a rejeicao de usos que poderiam duplicar a propriedade. Os testes historicos que proibiam qualquer campo dinamico foram atualizados para distinguir campo local seguro de lista de donos ainda nao suportada.

## Proximos contratos

1. Introduzir a representacao de valor agregado proprietario na analise de tipos e no fluxo de controle.
2. Permitir movimentar o registro inteiro atomicamente, com inativacao de todos os campos na origem e sem copiar descritores ativos.
3. Permitir registros proprietarios em parametros, retornos e listas, somente apos implementar destruicao/transferencia por elemento e seus testes em falhas/retornos antecipados.
4. Permitir tipo de resultado que contenha valor dinamico, sem fazer copia superficial da propriedade.
5. Provar ausencia de dupla liberacao, vazamento, referencias vencidas e regressao de ABI em ambos os alvos nativos. Sempre ampliar a cobertura de casos de erro antes de relaxar os bloqueios.

A sintaxe e os nomes sob controle do projeto seguem portugues brasileiro com identificadores sem acento. Os arquivos de codigo sao escritos com nomes em portugues brasileiro.
