# RS 0.32 — Listas dinâmicas com propriedade única

## Motivação

Até a RS 0.31, uma declaração como `lista[5]` reservava cinco posições fixas no quadro de execução. A RS 0.32 introduz **`lista[]`**, com quantidade de elementos variável, capacidade aumentada conforme a necessidade e armazenamento obtido diretamente do sistema operacional.

```text
inicio {
    seja numeros: lista[]
    adicione(numeros, 10)
    adicione(numeros, 20)
    escreva(tamanho(numeros))
    escreva(numeros[1])
}
```

Saída: 2 e 20 em linhas distintas. Não há capacidade máxima arbitrária escrita no código RS; o tamanho depende dos limites reais de endereçamento, memória, recursos do sistema e da proteção contra transbordamento.

## Comandos e comportamento

| Sintaxe | Função |
|---|---|
| `seja valores: lista[]` | Cria uma lista vazia com propriedade exclusiva |
| `adicione(valores, inteiro)` | Anexa um valor e aumenta a capacidade quando necessário |
| `tamanho(valores)` | Quantidade de posições ocupadas |
| `capacidade(valores)` | Quantidade de posições que cabem sem realocação |
| `valores[indice]` | Lê posição existente, com verificação de limites |
| `valores[indice] = inteiro` | Substitui posição existente, com verificação de limites |
| `leia(valores[indice])` | Lê um inteiro do teclado para posição existente, no bloco principal |
| `remova_ultimo(valores)` | Remove último elemento; erro se a lista estiver vazia |
| `limpe_lista(valores)` | Esvazia sem necessariamente desalocar a capacidade |
| `libere(valores)` | Devolve a memória ao sistema; a lista torna-se inutilizável |

A capacidade inicia em zero, cresce para quatro e dobra quando necessário. Esta é uma **política interna**, não um limite de tamanho imposto pelo programador. Não existe operação de inserção por índice fora do intervalo já preenchido: utilize `adicione` para aumentar a quantidade.

## Propriedade e tempo de vida

Cada `lista[]` possui **um dono exclusivo**. O compilador proíbe cópias implícitas (`seja outra = lista`, `lista = outra`), o uso como tipo de parâmetro/retorno de função e o armazenamento como campo de registro. Isso impede a duplicação acidental do ponteiro e duas liberações da mesma região. Ainda não há transferência explícita de propriedade nem referências emprestadas.

Listas são permitidas no nível principal de `inicio` ou do corpo da função; a declaração dentro de condicionais e laços permanece proibida nesta etapa. A memória é liberada ao finalizar o corpo do proprietário, mesmo em funções com retorno antecipado. O comando `libere` também está disponível; qualquer acesso posterior, inclusive `tamanho`, resulta em erro nativo controlado. Ao encerrar a função ou o programa, a liberação automática não tenta liberar novamente uma lista já liberada.

Listas fixas `lista[N]` continuam funcionando e **não mudam de significado**.

## Implementação nativa

O gerador x86-64 usa um descritor de três palavras (ponteiro, quantidade e capacidade), reservado no quadro de execução. Os elementos ficam em região separada solicitada ao sistema operacional:

- **Linux:** chamadas de sistema `mmap` e `munmap`.
- **Windows:** `VirtualAlloc` e `VirtualFree` da biblioteca do sistema, sem vinculação a biblioteca RS externa.

Ao crescer, o gerador cria outra região, copia os valores existentes e devolve a anterior. O código testa índices negativos, índices além do comprimento, lista liberada, impossibilidade de alocação e transbordamento no cálculo de bytes.

## Limitações reais

- Elementos de `lista[]` são somente `inteiro` de 64 bits nesta etapa; não existe `lista[MeuTipo]` dinâmica nem crescimento de textos.
- Não há empréstimos, referências públicas, transferência de propriedade, passagem de listas dinâmicas como argumento ou retorno.
- Listas declaradas em laços ou blocos condicionais não são permitidas ainda; esta restrição será removida com a análise completa dos pontos de saída de escopo.
- Não há garantia de operação quando o sistema ficar sem memória, além de encerrar com mensagem de erro clara. A política de realocação é de crescimento geométrico, não a promessa de jamais realocar.
- O compilador segue experimental. Não é adequado para produção; são necessárias auditorias adicionais do gerador, do alinhamento e dos caminhos excepcionais.
- Os níveis de otimização continuam `-O 0` até `-O 8`; para os recursos novos, a geração conservadora permanece em uso.

## Testes

No Windows:

```powershell
py -3 compilar.py exemplos\listas_dinamicas.rts --alvo windows -O 8 -o roteiro_windows.exe
.\roteiro_windows.exe
py -3 -m unittest discover -s testes -v
```

No Linux:

```bash
python3 compilar.py exemplos/listas_dinamicas.rts --alvo linux -O 8 -o roteiro_linux
./roteiro_linux
python3 -m unittest discover -s testes -v
```

Tudo que controlamos nesta implementação utiliza terminologia de português brasileiro; as palavras reservadas e os identificadores estão sem acentos, enquanto comentários, mensagens e documentação preservam UTF-8.
