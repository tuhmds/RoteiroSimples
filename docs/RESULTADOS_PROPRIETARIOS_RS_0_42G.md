# RS 0.42G — Resultados com propriedade

Esta nota descreve o marco 0.42G. A [0.42H acrescentou coleções proprietárias](COLECOES_PROPRIETARIAS_RS_0_42H.md), incluindo listas em campos de registros; os limites abaixo relativos a coleções descrevem a entrega original.

## Tipos e construção

`resultado[texto]`, `resultado[bytes]` e `resultado[MeuRegistro]` com campos
proprietários agora transportam donos. Registros podem conter texto, bytes,
listas de inteiros/lógicos e subregistros já suportados pela RS 0.42F.
Resultados de valores copiáveis existentes preservam sua semântica.

```text
funcao criar(escolha: logico) -> resultado[texto] {
    se escolha == falso {
        retorne falha[texto](7)
    }
    seja titulo: texto
    copie(titulo, "Relatório RS")
    retorne sucesso[texto](mova(titulo))
}
inicio {
    seja resposta = criar(verdadeiro)
    se resposta.valido {
        seja titulo = mova(resposta.valor)
        escreva(titulo)
    }
}
```

`sucesso[T]` recebe o dono com `mova(origem)` ou uma chamada que devolva um
valor novo de tipo T. O construtor movimenta o valor para o campo `valor` e
devolve o resultado inteiro por transferência. Não duplica o conteúdo nem
aloca outro heap só para transportá-lo.

`falha[T](codigo)` devolve `valido = falso`, conteúdo vazio/zerado e o código
informado. Código zero continua sendo normalizado para 2; códigos negativos
mantêm o comportamento histórico. A construção da falha não aloca conteúdo
dinâmico. Os descritores vazios têm comprimento e capacidade zero e ponteiro
nulo, permitindo transportar e descartar o resultado de falha normalmente.

Um sucesso com conteúdo vazio continua distinto de uma falha: consulte
`valido` e `codigo_erro`, não apenas o comprimento do conteúdo.

## Transporte, extração e descarte

O tipo concreto especializado continua um registro com `valido`, `valor` e
`codigo_erro`. Quando T possui donos, o resultado inteiro também é proprietário,
inclusive no estado de falha. Parâmetros, retornos e novas declarações exigem
`mova(resultado)` ou uma chamada nova. Cópias implícitas são rejeitadas.

Para retirar o valor, use `seja valor = mova(resposta.valor)` após verificar
`resposta.valido`. O campo fica inativo na origem. A limpeza do resultado
ignora esse campo já transferido; o valor retirado passa a ser descartado
pelo novo dono. Acesso ou novo movimento de conteúdo inativo gera o erro
controlado existente. Um resultado com qualquer folha já retirada não pode
ser transferido inteiro sem receber explicitamente os donos de volta.

Os campos escalares de estado continuam públicos e mutáveis por compatibilidade.
Extrair `valor` não altera automaticamente `valido`; essa marca não substitui
a verificação de vida do dono. Este marco conserva a representação histórica
de registro, sem introduzir uma união opaca. O valor de uma falha é vazio;
a aplicação deve consultar o estado antes de tratá-lo como um sucesso.

Cópias profundas de conteúdo seguem explícitas, como `copie(copia, resposta.valor)`
para texto/bytes. Empréstimos de leitura do conteúdo são permitidos durante
chamadas. Consumir o resultado e emprestar ou consumir seu campo na mesma
árvore de chamada continua rejeitado pela análise das folhas sobrepostas.

## Propagação

`propague resposta` mantém o contrato histórico:

- em sucesso, continua sem consumir ou extrair o valor;
- em falha, devolve uma falha do tipo de retorno atual com o mesmo código;
- ao sair por falha, descarta os donos restantes do resultado e dos demais
  parâmetros, temporários e locais da função.

O tipo propagado pode diferir do retorno, incluindo valor copiável para
proprietário, proprietário para copiável e proprietários de tipos distintos.
Isso permite, por exemplo, propagar uma rejeição de título para
`resultado[Documento]`. Depois de extrair o conteúdo de um sucesso, reembale
com `sucesso[T](mova(valor))` ou devolva o valor no tipo apropriado.

Falhas aritméticas, índices inválidos, conteúdo UTF-8 inválido, falha de
alocação e erros nativos fatais continuam com seus comportamentos existentes.
`propague` não os captura automaticamente. Erros recuperáveis precisam ser
produzidos explicitamente pelas funções, conforme seus contratos.

## Implementação

A especialização resolve as declarações concretas com o analisador de tipos
existente e consulta `contrato_valor`. Esse passo estático analisa apenas
declarações, sem executar código RS nem gerar executável intermediário.
Os construtores copiáveis mantêm atribuição/retorno por valor; os proprietários
usam `mova` tanto no recebimento quanto no retorno.

O gerador conservador, a disposição de registros, os descritores, o alocador,
o descarte por escopo e os metadados Windows permanecem compartilhados com
a RS 0.42F. Não foi introduzido outro gerenciador de memória ou runtime.
Executáveis PE/ELF permanecem independentes de Python. O0–O8 continuam iguais.

## Biblioteca demonstrativa em RS

`importe "padrao/documentos.rts" como documentos` oferece `Documento`,
`validar_titulo`, `validar_conteudo`, `criar` e `alterar_titulo`.
Título é texto UTF-8 e conteúdo é binário, sem conversão implícita.
Os limites recebidos são em bytes. Códigos de falha:

| Código | Significado |
|---|---|
| 1 | Título vazio |
| 2 | Limite de título inválido ou título acima do limite |
| 3 | Limite de conteúdo negativo ou conteúdo acima do limite |

Conteúdo vazio é válido quando cabe no limite. As funções consomem os
parâmetros recebidos, também quando devolvem falha. Em `criar`, rejeitar o
título descarta o conteúdo ainda não validado; rejeitar o conteúdo descarta
o título já validado. `alterar_titulo` descarta o título antigo ao substituí-lo
e conserva o conteúdo; se a validação falhar, descarta o documento consumido.
Não há compromisso de devolver as entradas ao chamador no caminho de falha.

O exemplo `exemplos/aplicacoes/documento_resultado_rs042g.rts` rejeita um título
vazio e continua no mesmo processo para produzir um documento válido com
texto acentuado e bytes NUL/255. Essa biblioteca demonstra composição de
resultados proprietários; não implementa um formato persistente ou banco.

## Verificação e limites

```text
python -m unittest testes.test_resultados_proprietarios_rs042g -v
python -m unittest testes.test_abi_resultados_proprietarios_rs042g -v
python -m unittest discover -s testes -v
python compilar.py exemplos/aplicacoes/documento_resultado_rs042g.rts --alvo windows -O 8 -o documento.exe
```

Para Linux, use `--alvo linux` e execute o ELF x86-64. Os cenários centrais
de texto, bytes, registros aninhados, biblioteca e compatibilidade percorrem
os nove níveis; os demais usam O0/O8. Ambos os formatos são gerados e cada
sistema executa seu formato nativo na CI. Há rejeições de cópia, atribuição,
consumo sobreposto, empréstimos incompatíveis e tipos distintos, além de
propagação entre tipos, escopos, estado parcial e limite de recursão.

O Windows real verifica identidade de dois heaps, ponteiros liberados,
construção de falha sem alocação, limpeza após propagação e extração/reembalagem.
O percurso completo termina com doze alocações e doze liberações. Também
verifica oito registradores inteiros, dez vetoriais não voláteis, RSP,
estados de desenrolamento e exceções reais nos construtores e funções.

Ainda não são suportados resultados aninhados, resultados diretos de listas
dinâmicas, `resultado[bytes[N]]`, resultados de empréstimos/recursos arquivo,
coleções de registros proprietários ou empréstimos de registros completos.
Não há funções genéricas gerais, empréstimos mutáveis ou alterações de FFI.
O motor Dados RS, o Studio e a autocompilação continuam entregas futuras.
