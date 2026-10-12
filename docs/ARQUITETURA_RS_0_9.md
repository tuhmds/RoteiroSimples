# Arquitetura do compilador — RS 0.9

Esta versão reorganiza **módulos reais** e mantém os executáveis produzidos pela RS 0.8.

```text
compilar.py
  → compilador.lexico (tokens)
  → compilador.parser (blocos, laços, declarações)
      → compilador.expressoes (precedência)
      → compilador.semantica (símbolos, validação)
      → compilador.tipos (inteiro, logico)
      → compilador.ast (Programa, AST em tuplas)
  → backend.compilar
      → compilador.ir (conversão para IR e adaptador)
          → compilador.nos_ir (nós tipados e imutáveis)
          → compilador.otimizador (constantes seguras)
      → backend.x86_64 (instruções AMD64 nativas)
      → backend.linux_elf / backend.windows_pe
  → executável ELF64 ou PE32+
```

## Responsabilidades e contratos

| Módulo | Responsabilidade |
|---|---|
| `compilador/lexico.py` | Tokenização: palavras reservadas e nomes ASCII; strings UTF-8 |
| `compilador/expressoes.py` | Análise sintática de expressões e precedência |
| `compilador/parser.py` | Decisões, laços, leitura, saída e declarações |
| `compilador/semantica.py` | Tabela de símbolos, conferência de tipos e atribuições |
| `compilador/tipos.py` | Verificação estática de `inteiro` e `logico` |
| `compilador/ast.py` | Estrutura do programa; os nós ainda são tuplas |
| `compilador/nos_ir.py` | Nós imutáveis da IR tipada |
| `compilador/ir.py` | AST → IR e adaptador temporário para AST legada |
| `compilador/otimizador.py` | Dobramento de constantes sem omitir erros |
| `backend/base.py` | Emissão de bytes e referências relativas |
| `backend/x86_64.py` | Instruções, cálculo, fluxo e rotinas de E/S nativas |
| `backend/linux_elf.py` | Empacotamento ELF64 Linux |
| `backend/windows_pe.py` | Empacotamento PE32+ Windows |
| `backend/__init__.py` | Orquestra conversão IR → código nativo |

## Compatibilidade e testes

Os arquivos `sintaxe.py`, `ir.py` e `codigo_nativo.py` continuam como fachadas para importações existentes.
Não é necessário modificar programas `.rts`. O compilador ainda usa Python 3, mas os executáveis compilados não.

`testes/fixtures/rs08_binarios.json` contém **36 SHA-256** de executáveis: nove exemplos existentes, dois sistemas e dois níveis de otimização. O teste de regressão confere que a arquitetura nova não altera esses bytes. A integração contínua executa os testes no Windows e Linux.

## Limitações e próximos passos

Ainda não há AST com metadados completos de origem, CFG, SSA, análise global de fluxo, alocador de registradores, objetos/linker separados, runtime completo, heap, ponteiros ou ARM64. O backend recebe uma AST reconstruída a partir da IR; essa transição deve ser substituída gradualmente, não removida de uma vez. O projeto segue experimental e não deve ser usado em produção.

Próxima etapa sugerida: posições de origem em nós AST, depois grafo de fluxo de controle e testes de equivalência para otimizações entre blocos.
