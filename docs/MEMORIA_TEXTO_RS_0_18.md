# RoteiroSimples RS 0.18 — buffers de texto e proposta de referências

> A RS é experimental. Este documento separa a implementação efetiva das regras **propostas** para versões futuras.

## Buffers UTF-8 implementados

```text
inicio {
    seja mensagem: texto[48]
    copie(mensagem, "Olá, ")
    junte(mensagem, "mundo 🌎")
    escreva(mensagem)
    escreva(tamanho(mensagem))
    escreva(capacidade(mensagem))
    limpe(mensagem)
    leia(mensagem)
    escreva(mensagem)
}
```

- `texto[N]` é um **buffer local de bytes UTF-8**, de capacidade `N` constante (1 a 2040), sujeito ao limite total de **256 slots de 8 bytes** da pilha (soma com outras variáveis e listas).
- O compilador reserva um slot de oito bytes para o **comprimento** e `ceil(N/8)` slots para os bytes de conteúdo, fisicamente contíguos na pilha.
- `tamanho(mensagem)` lê o comprimento corrente **em bytes**; `capacidade(mensagem)` é a quantidade máxima de bytes. A letra `á` ocupa 2 bytes, e o emoji `🌎` ocupa 4 bytes. **Não** é a contagem de pontos de código nem de caracteres percebidos.
- `copie(destino, "literal")` / `copie(destino, origem)` substituem o conteúdo; `junte` concatena. Nenhuma operação trunca conteúdo. Uma cópia literal grande demais é rejeitada na compilação; outras ultrapassagens encerram o programa com código 1 e mensagem de erro.
- `limpe(buffer)` define comprimento zero; não promete apagar fisicamente os bytes antigos, então não deve ser usado como limpeza de segredos.
- `escreva(buffer)` imprime somente `tamanho(buffer)` bytes, seguido de `\n` (sem depender de terminador NUL).
- `leia(buffer)` recebe uma linha de **stdin**, remove o `\n` e um eventual `\r` imediatamente anterior, aceita EOF com texto vazio e rejeita caracteres UTF-8 malformados, não terminados, sequências excessivamente longas ou entradas maiores que a capacidade. Essa leitura é implementada pelo executável nativo, sem Python em runtime.
- Literais e nomes seguem as regras existentes: comandos e identificadores ASCII sem acentos; os conteúdos dos textos continuam UTF-8.
- Os buffers usam temporariamente o backend de **pilha com proteção de capacidade**, em todos os níveis `-O 0` a `-O 6`. A SSA de registradores e as análises CFG/SSA ainda não modelam os efeitos desses buffers; permanecem indisponíveis para programas que os utilizem.
- Não existe aritmética de ponteiros, índice direto em texto, substring, alocação dinâmica, texto de tamanho arbitrário ou normalização Unicode implícita. O formato interno não é uma ABI pública.
- **Limitação de desempenho:** a leitura faz uma chamada ao sistema por byte. Escritas ainda não repetem automaticamente operações parciais (`write` / `WriteFile`), e o formato PE ainda limita seções a 4 KiB. Futuras versões deverão implementar I/O em blocos e tratamento robusto de escritas parciais.

## Referências e empréstimos — PROPOSTA, NÃO IMPLEMENTADOS

Uma futura referência segura deve conter (ou permitir comprovar estaticamente) **objeto-alvo, comprimento, mutabilidade e validade temporal**. Queremos definir:

1. **Um dono por objeto** (listas e buffers na pilha enquanto existir o seu escopo; posterior suporte a heap com regra explícita).
2. **Empréstimos compartilhados**, potencialmente múltiplos, somente leitura.
3. **Empréstimo mutável exclusivo**, sem coexistir com referências compartilhadas ou mutáveis ativas sobre a mesma região.
4. **Sem referência após fim de vida** ou retorno de referência à variável local, com verificação de escopo/tempo de vida pelo compilador.
5. **Fatiamento limitado**, verificando limites de início/fim e preservando a relação com o objeto original.
6. **Ponteiros brutos somente em blocos explicitamente inseguros**, mais adiante, para interoperabilidade; nenhuma dessas operações integra a RS 0.18.

Não escolhemos ainda sintaxe definitiva para declaração ou empréstimo de referências. Não queremos reservar palavras ou impor regras de aliasing prematuramente sem testes.

## Próximos passos

- I/O bufferizado eficiente e cálculo de comprimento Unicode por pontos de código, separado do comprimento de bytes.
- Representação de operações com efeitos de memória na IR, SSA, dominância e análise de alias.
- Escopos reais, tipos compostos, tempo de vida e modelo de propriedade; só então introdução de referências seguras.
- Benchmarks e testes negativos de acesso fora dos limites, duplo empréstimo mutável e referência pendente.
