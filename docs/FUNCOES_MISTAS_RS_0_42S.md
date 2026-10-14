# RS 0.42S — Otimização por função em programas mistos

## Contrato

A presença de registros, donos, empréstimos ou arquivos continua impedindo
a IR do programa completo, mas já não impede otimizar suas funções escalares
independentes. O início permanece conservador. A estratégia `misto` combina
os corpos elegíveis com os demais corpos no mesmo executável PE/ELF.

Uma função é elegível quando retorno, parâmetros e variáveis locais são
`inteiro` ou `logico`, todas as operações possuem representação na IR e
todas as chamadas pertencem ao grupo escalar elegível. A classificação
visita argumentos, blocos e trechos inacessíveis. Uma restrição elimina
também os chamadores que dependem dela; ciclos escalares e recursão mútua
permanecem elegíveis quando não dependem de funções recusadas.

Este marco permite **chamador conservador -> função escalar otimizada** e
**função escalar otimizada -> função escalar otimizada**. Uma função escalar
que chama um corpo conservador fica conservadora também. Não há otimização
de acessos a campos, descritores proprietários ou operações de arquivo.
Impressão e falhas aritméticas do contrato escalar continuam permitidas:
elegibilidade não significa ausência de efeitos.

| Nível em programa misto | Emissão das funções elegíveis |
| --- | --- |
| O0 / otimização desativada | Emissão conservadora anterior, com os mesmos bytes |
| O1 | IR com dobramento seguro de constantes; emissão conservadora do corpo transformado |
| O2 | Acrescenta propagação local |
| O3 | Acrescenta propagação SSA por corpo, sem eliminar ou mover chamadas |
| O4 | SSA e alocação nativa por função |
| O5 | Organização dos blocos |
| O6–O8 | Preferências de alocação, cópias de phi e compactação dos saltos SSA |

`nivel_ir=0` na decisão global descreve o início conservador; os registros
`funcoes` informam os níveis efetivos de cada corpo. O7/O8 não acrescentam
transformações de memória a esse subconjunto. Não há novo nível de otimização.
Sem funções elegíveis o programa continua totalmente conservador.
Programas inteiramente escalares conservam o caminho anterior da 0.42L.

## Implementação e chamadas

`compilador/funcoes_mistas.py` classifica os corpos e suas dependências.
`GrupoFuncoesIR` contém somente funções, sem criar uma IR vazia que aparente
representar o início. Conversão e propagação são compartilhadas com o caminho
completo; a SSA parcial valida as assinaturas e os usos.

`backend/funcoes_mistas.py` conserva o início, os registros e as funções
recusadas da AST original. Substitui somente as funções selecionadas, usando
cópias: compilar o mesmo programa novamente não altera tipos, variáveis ou
instruções do objeto original. A preparação do quadro SSA é a mesma utilizada
pelo backend de funções escalares completas.

A convenção de argumentos por valor, retorno em RAX, orçamento acumulado de
pilha, sondagem e metadados Windows permanece comum. No Linux, as vagas de
salvamento dos registradores SSA continuam separadas das casas dos parâmetros
e dos temporários. Chamadores conservadores continuam responsáveis por seus
donos, empréstimos e recursos, com descarte pelo caminho existente. Argumentos
continuam avaliados na ordem original, inclusive quando não usados pelo chamado.

## Diagnósticos e reprodução

```text
python compilar.py benchmarks/colecoes_mistas_rs042s.rts -O 8 --mostrar-estrategia --mostrar-ir --mostrar-ssa --mostrar-alocacao -o colecoes.exe
python compilar.py exemplos/ferramentas/analisador_lexico_rs042c.rts -O 8 --mostrar-estrategia --salvar-ssa lexico-ssa.json -o lexico.exe
python -m unittest testes.test_funcoes_mistas_rs042s testes.test_abi_funcoes_mistas_rs042s -v
python -m benchmarks.medir --fonte benchmarks/lexico_rs042s.rts --repeticoes 17 --json lexico.json
python -m benchmarks.medir --fonte benchmarks/colecoes_mistas_rs042s.rts --repeticoes 17 --json colecoes.json
```

Use `--alvo linux` e nomes sem `.exe` para emitir ELF. Os ensaios de execução
e ABI usam o sistema nativo correspondente.

Nos programas mistos, `--mostrar-estrategia` lista cada função e o motivo da
recusa. IR/SSA/alocação e cópias de phi indicam explicitamente análise parcial.
A exportação SSA usa `principal: null`, inclui somente os corpos elegíveis e
identifica o modo parcial. Exportar SSA em O0 não muda a emissão conservadora.
CFG, fluxo, efeitos IR e memória versionada do programa completo continuam
indisponíveis nesse caminho; use `--mostrar-efeitos-do-programa` para os efeitos
da AST completa. Os corpos omitidos podem ser identificados no relatório de
estratégia. `construir_ir` continua recusando uma tradução completa incompatível.

## Verificação e limites das medições

Os testes incluem recusas transitivas, ciclos, operações desconhecidas, grupos
incompletos, AST preservada e bytes O0, chamadas feitas por donos, consultas a
coleções, entrada, arquivos, curto-circuito, argumentos não usados, falhas
aritméticas e limite de recursão. Doze programas gerados confrontam os nove
níveis com um cálculo Python independente. O léxico em RS é confrontado com
o léxico Python, incluindo posições em bytes.

Ensaios Windows em processos isolados verificam oito registradores inteiros,
dez vetoriais, RSP, `RtlVirtualUnwind`, exceções INT3 reais e sondagem em função
SSA com quadro maior que uma página. O ensaio Linux confronta os seis
registradores não voláteis e RSP ao chamar um corpo conservador que possui
texto e chama código SSA. A CI cobre Windows/Linux e Python 3.10/3.11/3.14.

Dois programas RS medem léxico e consulta de registros com cálculo escalar.
As saídas esperadas têm oráculos separados nos testes. As medições nativas
intercalam O0–O8, com aquecimento, tempos individuais, hashes de executáveis,
compilação separada e decisões por função no JSON. A campanha de crescimento
continua coletando memória da compilação em uma amostra separada dos tempos.
Memória Python não mede a memória da aplicação nativa. A família `misto`
dessa campanha testa uma função proprietária declarada e não executada;
os dois novos programas exercitam os recursos durante a execução.

O léxico otimiza quatro classificadores escalares. As bibliotecas atuais de
cadastro e persistência seguem conservadoras porque seus corpos manipulam
dados compostos, empréstimos ou recursos. Seus testes de gravação, reabertura,
formato, falhas e corrupção permanecem obrigatórios. Esta versão não amplia
as garantias de durabilidade da 0.42N.

O ganho de tempo depende do programa e da plataforma. Selecionar SSA não
garante que cada função seja mais rápida. Comparar os níveis exige observar
as amostras; não inferir desempenho pelo tamanho do executável. Dominância
ainda utiliza conjuntos com custo potencial quadrático. A evolução seguinte
da IR de recursos exige contratos próprios de memória, efeitos e propriedade.
