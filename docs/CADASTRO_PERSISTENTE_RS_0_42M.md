# RS 0.42M — UTF-8 explícito e cadastro persistente em RS

Esta etapa entrega três módulos escritos em RS e dois executáveis de exemplo.
O compilador acrescenta somente as operações nativas de conversão explícita.
O armazenamento é uma prova de snapshot completo para o Dados RS; seu formato
experimental não congela o formato do futuro motor.

## Conversão e propriedade

```text
inicio {
    seja nome: texto
    copie(nome, "Ação 🌱")
    seja dados: bytes
    seja volta: texto
    seja estado = 0
    codifique_utf8(dados, nome, estado)
    decodifique_utf8(volta, dados, estado)
    escreva(volta)
}
```

`codifique_utf8(destino_bytes, origem_texto, estado)` e
`decodifique_utf8(destino_texto, origem_bytes, estado)` recebem destinos
dinâmicos proprietários. A origem é uma variável ou campo, fixo, dinâmico
ou emprestado, da categoria correspondente. `estado` é uma variável inteira
simples. Destinos emprestados ou campos de registros emprestados são rejeitados.

Ambas validam UTF-8 estrito antes de copiar. Isso também permite rejeitar
conteúdo inválido carregado em um `texto[N]`. Não aceitam sequências
superlongas, substitutos Unicode, valores acima de U+10FFFF, continuações
isoladas ou sequências incompletas. ASCII, NUL, acentos, emoji e texto vazio
são aceitos. Não há normalização, BOM obrigatório ou substituição silenciosa.

Estado `0` indica sucesso; `1` indica UTF-8 inválido, com destino intacto.
A origem permanece ativa e inalterada. Em sucesso o conteúdo substitui o
destino por cópia independente, reutilizando sua capacidade quando possível.
`tamanho` continua contando bytes e `caracteres` valores escalares Unicode.
`copie` e `junte` continuam exigindo categorias compatíveis.

`padrao/utf8.rts` oferece `codificar(emprestimo[texto]) -> resultado[bytes]`
e `decodificar(emprestimo[bytes]) -> resultado[texto]`. Cada sucesso possui
seu próprio buffer; a falha devolve valor vazio e código `1`.
Falta de memória e uso de um dono inativo seguem os erros fatais existentes.
Somente a entrada UTF-8 inválida se torna recuperável nestas operações.

## Cadastro em memória

`padrao/cadastro_variavel.rts` define `Registro` com `codigo: inteiro`,
`titulo: texto` e `conteudo: bytes`; `Cadastro` contém `lista[Registro]`.

| Função pública | Contrato |
|---|---|
| `criar()` | cadastro vazio proprietário |
| `localizar(cadastro, chave)` | índice por código, ou `-1`; empréstimo |
| `pesquisar_titulo(cadastro, titulo)` | primeiro índice com bytes de título iguais, ou `-1`; empréstimos |
| `codigo(registro)`, `titulo_igual(registro, titulo)` | consultas por empréstimo |
| `adicionar(cadastro, registro)` | consome os dois e acrescenta se válido e único |
| `alterar(cadastro, registro)` | consome os dois; substitui o código existente, conservando a ordem |
| `remover(cadastro, chave)` | consome o cadastro; remove e descarta o registro encontrado |
| `serializar(cadastro)` | empréstimo; `resultado[bytes]` com nova cópia |
| `desserializar(dados)` | empréstimo; `resultado[Cadastro]` com novos donos |
| `tamanho_registro(registro)` | tamanho codificado, antes da validação |
| `verificar_integridade(dados, deslocamento)` | Adler-32 do sufixo; `-1` para deslocamento inválido |

As alterações retornam `ResultadoCadastro` com `valido`, `codigo_erro` e
`valor`. **Recupere `valor` tanto em sucesso quanto em falha.** Uma alteração
rejeitada conserva os registros anteriores no cadastro devolvido; o registro
de entrada rejeitado é consumido e descartado. Os campos públicos continuam
mutáveis, portanto a serialização revalida o cadastro antes de gravar.

```text
seja resposta = cad.adicionar(mova(cadastro), mova(registro))
se resposta.valido == falso {
    escreva(resposta.codigo_erro)
}
mova(cadastro, resposta.valor)
```

## Formato RSCV versão 1

Inteiros são little-endian, sem ponteiros, capacidade de heap, alinhamento
de registro ou dependência da ABI. O cabeçalho ocupa 24 bytes:

| Deslocamento | Campo | Tamanho |
|---:|---|---:|
| 0 | identificação `RSCV` | 4 bytes |
| 4 | versão `1` | u32 |
| 8 | quantidade de registros | u32 |
| 12 | comprimento do corpo | u32 |
| 16 | Adler-32 do corpo | u32 |
| 20 | reservado `0` | u32 |

Cada registro ocupa `16 + bytes_do_titulo + bytes_do_conteudo`:
código u64 positivo, comprimento do título u32, comprimento do conteúdo u32,
título em UTF-8 estrito e conteúdo binário bruto. Código de `1` até
`9223372036854775807`, título de 1 a 1024 bytes, conteúdo de 0 a 65536 bytes,
até 1024 registros e até 8388608 bytes no arquivo completo.

A leitura valida o cabeçalho, tamanho exato do corpo e integridade antes de
reconstruir registros. Verifica o espaço restante antes de cada cópia,
rejeita códigos repetidos e bytes excedentes e descarta construções parciais
ao falhar. O cabeçalho e o prefixo de registro já têm tamanho verificado
antes das leituras u32. Adler-32 detecta corrupção acidental; não autentica
arquivos nem protege contra alterações deliberadas com soma recalculada.

## Persistência e erros

`padrao/cadastro_arquivo.rts` oferece `salvar(cadastro)` por empréstimo e
`carregar()`. Nesta prova, os nomes são fixos: `cadastro_provisorio.rsd` e
`cadastro.rsd`, no diretório corrente. A publicação existente aceita nomes
literais. Não há configuração de diretório ou acesso simultâneo coordenado.

Salvar primeiro valida e serializa, depois abre o provisório com criação
exclusiva, escreve blocos de 4096 bytes, sincroniza, fecha e publica por
renomeação. Falhas antes da publicação preservam o destino anterior.
Um provisório existente é recusado, sem sobrescrita; após falha, pode
permanecer parcial ou completo para inspeção. Sua recuperação é manual.

Carregar usa leitura posicional recuperável e limita a entrada antes de
acrescentá-la ao buffer. Ao alcançar 8 MiB, lê no máximo mais um byte para
detectar excesso. Retornos antecipados fecham o recurso pelo descarte de
escopo. O fechamento normal é explícito para comunicar seu erro. Um diretório
é rejeitado na abertura no Windows e na transferência no Linux, com os
códigos correspondentes a cada etapa.

| Código | Motivo |
|---:|---|
| 1 / 2 / 3 | código, título ou conteúdo fora dos limites |
| 4 / 5 / 6 | coleção cheia, código repetido ou código ausente na alteração |
| 10 / 11 / 12 / 13 | cabeçalho curto, identificação, versão ou campo reservado inválido |
| 14 / 15 / 16 | limite global, comprimento do corpo ou integridade inválida |
| 17 / 18 / 19 / 20 / 21 | campo truncado ou excedente, limite de campo, código inválido, duplicado ou UTF-8 inválido |
| 30 / 31 / 32 / 33 / 34 | abertura, transferência, sincronização, fechamento ou publicação |
| 35 | publicação ocorreu, mas a sincronização do diretório falhou no Linux |

Código `35` exige conferir o arquivo publicado: não significa que o destino
anterior foi preservado. Não há promessa de transações, ACID, diário,
recuperação automática após interrupção, índices ou durabilidade absoluta.

## Execução e verificação

```text
python compilar.py exemplos/dados_rs/cadastro_gravar_rs042m.rts --alvo windows -O 8 -o gravar.exe
python compilar.py exemplos/dados_rs/cadastro_ler_rs042m.rts --alvo windows -O 8 -o ler.exe
./gravar.exe
./ler.exe
```

No Linux, use `--alvo linux` e nomes sem `.exe`. Execute ambos no mesmo
diretório de trabalho. O gravador acrescenta três registros, altera um,
remove outro e salva dois; o leitor mostra os campos por empréstimo e busca
o título atualizado. O arquivo tem 5343 bytes. Os executáveis não exigem
Python, C, LLVM, montador ou máquina virtual para funcionar.

Os testes comparam UTF-8 com Python e o formato com `struct`/`zlib` como
oráculos independentes. Cobrem O0–O8, reabertura por outro processo, limites,
mutação de arquivos, soma recalculada com campos inválidos, erros de arquivo
e gravação parcial. No Windows há ensaios reais de descartes, oito
registradores inteiros, dez vetoriais e RSP, desenrolamento e exceções INT3.
No Linux, limite de tamanho do sistema provoca escrita parcial real.
A CI executa esses testes nas três versões Python de cada sistema.

Os recursos proprietários continuam no gerador conservador. As consultas
são lineares; a validação de unicidade é quadrática. Serialização e leitura
criam cópias e podem manter vários buffers simultâneos. Limite do arquivo
não é um orçamento de memória do processo. O próximo passo do armazenamento
é especificar recuperação e concorrência antes de aumentar estas garantias.
