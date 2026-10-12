# Fundação da linguagem — RoteiroSimples RS 0.23

## Escopos léxicos

Cada bloco `se`, `senao`, `enquanto` ou `para` tem nomes locais próprios.
Uma variável pode ocultar uma variável externa de mesmo nome, sem modificar
a externa. Ao sair do bloco, o nome local deixa de ser acessível. A identidade
interna da variável é distinta, com posição independente no quadro de pilha.
A duração física dos slots é a execução do quadro; **a reutilização de slots
não está implementada**. Por compatibilidade histórica, um contador criado
implicitamente por `para` é declarado no bloco envolvente.

## Funções nativas

Declarações `funcao nome(parametro: inteiro, outro: logico) -> inteiro { ... }`
precedem `inicio`. As funções têm escopos independentes, parâmetros e retorno
obrigatório, além de chamadas nativas x86-64 com instruções reais CALL/RET.
O compilador usa convenção privada de chamada com argumentos na pilha; **ela
não é uma interface ABI pública** e não substitui interoperabilidade com C.

A verificação é estática: nomes duplicados, argumentos ausentes, tipos errados,
retornos incompletos e recursão direta/indireta são rejeitados. Recursão e
entrada/saída por `leia` dentro de funções serão habilitadas após a definição
de um contrato de esgotamento de pilha, passagem de valores compostos e
tratamento uniforme de entrada. `escreva` é permitido em funções.

## Memória calculada por necessidade

- O antigo limite artificial de **256 posições locais** não é usado para
  impedir programas. Cada declaração incrementa o quadro de pilha conforme
  o seu tipo e tamanho.
- As seções PE do Windows usam endereços calculados a partir dos tamanhos reais.
  Programas maiores que 4 KiB de código são admitidos.
- A pilha é reservada com sondagem progressiva de páginas para quadros grandes
  no Windows e no Linux, sem prometer disponibilidade ilimitada.
- Listas e textos deixam de ter máximos artificiais de 256 posições e 2040
  bytes, mas continuam **com tamanho fixo**. Limites reais: deslocamento
  relativo de 32 bits do gerador x86-64 e memória disponível no processo.
- Listas e buffers grandes são inicializados com laços compactos. Leituras
  e escritas continuam passando por verificação dos limites.

## Limitações e próximos passos

1. Recursão com limites explícitos e funções capazes de receber listas/textos.
2. Tipos definidos pelo programador, tipos numéricos adicionais e escopo de módulos.
3. Valores alocados dinamicamente, referências e empréstimos verificados.
4. Adaptação da representação intermediária e dos otimizadores para chamadas e
   efeitos de memória entre quadros; atualmente usa-se o backend conservador.
5. Testes adicionais de limites sob diferentes configurações de pilha e
   recursos realmente disponíveis de Windows e Linux.

O compilador é experimental; não deve ser usado em sistemas de produção.
