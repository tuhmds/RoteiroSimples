# Princípios permanentes de independência e português brasileiro da RS

## Alcance real, sem propaganda enganosa

A RoteiroSimples é uma linguagem de programação em português
brasileiro que busca independência da cadeia externa de compilação.

**Já implementado:** a cadeia atual em Python emite diretamente ELF64
(Linux) e PE32+ (Windows), sem exigir C, LLVM ou montador externo. Os
executáveis não precisam de Python, da instalação do compilador RS,
nem de uma máquina virtual RS. Como programas nativos, usam as
interfaces do sistema operacional; independência não significa
funcionar sem Windows/Linux ou sem seus serviços.

**Ainda não implementado:** compilador autocompilado e cadeia completa
escrita em RS. Enquanto a implementação do compilador for Python,
não declarar a cadeia de desenvolvimento "100% independente". O
objetivo de longo prazo é construir o compilador em RS, com etapas
de conferência entre a implementação original e a autocompilada.

## Regras linguísticas

1. Sintaxe pública, palavras reservadas, funções, variáveis e tipos
   novos em português brasileiro **sem acentos nos identificadores**.
2. Nomes de novos módulos, diretórios, arquivos e testes sob nosso
   controle em português brasileiro. Prefira `disposicao_tipos.py`,
   não `layout_tipos.py`.
3. Mensagens de erro, comentários, documentação e exemplos em português
   brasileiro. Comentários e textos podem ter acentos; identificadores
   públicos da linguagem não.
4. APIs e nomes externos obrigatórios de sistema ou arquivo (Windows,
   Linux, ELF, PE, `CreateFileA`, `fsync`, extensões e convenções
   de compatibilidade) continuam com seus nomes definidos externamente.
   `README.md` é convenção reconhecida pelo GitHub.
5. Identificadores históricos já existentes como `backend`,
   `parser.py` e `MAX_VARIAVEIS` precisam de inventário e plano
   de migração, com aliases transicionais quando necessário; não
   quebrar programas antigos apenas para renomear internamente.
6. Bibliotecas que podem ser escritas em RS devem ser escritas em RS.
   A implementação original do compilador, seus testes e ferramentas
   temporárias podem continuar em Python durante a transição para
   autocompilação; são ferramentas de **construção**, não dependências
   de **execução**.
7. Não adicionar dependência obrigatória de C, LLVM, Rust, JavaScript,
   um runtime externo, ou uma infraestrutura estrangeira só para
   facilitar a implementação. Quando interoperabilidade externa for
   necessária, ela será explícita, opcional, documentada e isolada.
8. Recursos internos devem usar módulos pequenos com responsabilidades
   claras, conservando a emissão nativa e a segurança sem duplicar
   regras de layout, propriedade e erros.

## Verificação a cada versão

- O executável funciona no Windows/Linux sem Python e sem compilador RS
  instalado na máquina de execução.
- Nenhuma dependência nova de execução obrigatória foi introduzida.
- Todos os novos nomes controlados pelo projeto obedecem às convenções
  em português, identificadores sem acentos.
- A versão documenta claramente quais metas ainda não foram atingidas.
- A integração contínua compila e executa casos reais nos dois sistemas.

A linguagem RS **não tem** hoje compilador autocompilado. A regra é
um compromisso de arquitetura e uma meta objetiva de engenharia,
não uma alegação de conclusão antecipada.
