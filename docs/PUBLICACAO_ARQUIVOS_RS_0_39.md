# RS 0.39 — Publicação por renomeação, caminhos variáveis e bloqueios

## 1. Objetivo

Construir aplicações de armazenamento que prepararem uma versão nova de um
arquivo sem sobrescrever ou truncar diretamente a versão publicada. Esta
versão trabalha com **arquivos inteiros** e evita declarar a RS um sistema
de transações ou um motor de banco de dados.

Executáveis continuam nativos para Windows x64 e Linux x86-64; Python é
utilizado no compilador e no ambiente de testes, não pelos executáveis.

## 2. Publicação: preparar -> sincronizar -> fechar -> trocar

Uso típico:

\`\`\`text
inicio {
    seja rascunho: arquivo
    seja dados: bytes[16]
    seja estado = 0
    abra_arquivo("rascunho.rsd", rascunho, "novo", estado)
    se estado != 0 {
        encerre(1)
    }
    adicione_byte(dados, 82)
    grave_em(rascunho, dados, 0, estado)
    se estado != tamanho(dados) {
        encerre(2)
    }
    sincronize_arquivo(rascunho, estado)
    se estado != 0 {
        encerre(3)
    }
    feche_arquivo(rascunho, estado)
    se estado != 0 {
        encerre(4)
    }
    publique_arquivo("rascunho.rsd", "banco.rsd", estado)
    se estado != 0 {
        encerre(5)
    }
}
\`\`\`

\`publique_arquivo("provisorio","publicado",estado)\` recebe nomes
**literais** de arquivos no mesmo diretório de execução, com um único
componente ASCII. A origem deve existir, ter sido fechada e idealmente
sincronizada. A operação tenta substituir o destino, se ele existir.
Não aceita nomes idênticos, barras, \`.\`, \`..\`, caminhos absolutos nem
nomes reservados de dispositivos Windows.

### Implementação e garantias

- **Linux:** \`renameat(AT_FDCWD,...)\`, em seguida \`fsync\` do
  diretório atual usando \`openat\` com \`O_DIRECTORY|O_CLOEXEC\`.
  Renomear dentro de um único sistema de arquivos dá publicação
  de nome atômica para observadores, observadas as garantias locais
  de \`renameat\`. \`fsync\` de diretório melhora a persistência da
  alteração de nome.
- **Windows:** \`MoveFileExA\` com \`MOVEFILE_REPLACE_EXISTING\` e
  \`MOVEFILE_WRITE_THROUGH\`, sem \`MOVEFILE_COPY_ALLOWED\`.
  Essa solicitação pode falhar se leitores mantiverem identificadores
  exclusivos, e **não equivale a uma prova de atomicidade e durabilidade
  em todos os sistemas de arquivos/volumes**.
- **Sucesso:** estado \`0\`.
- **Falha de troca:** \`-8\`; a versão de destino anterior não deve
  ser considerada substituída sem verificar o estado.
- **Falha de sincronização do diretório (Linux):** \`-9\`; atenção,
  **a troca pode já estar visível**. Não repita o comando ingenuamente,
  porque o nome provisório pode ter desaparecido.

O código não fornece detecção de perda de energia, transação, diário
WAL, política de backup nem testes reais com o desligamento físico da
máquina. Não promete \`ACID\`. A validação atual injeta falhas
determinísticas por encerramento de processo antes e depois da publicação.

## 3. Bloqueio não bloqueante

\`bloqueie_arquivo(arquivo,estado)\` recebe recurso aberto e retorna
\`0\` se o bloqueio/condição de exclusividade foi adquirido, ou \`-7\`
se o bloqueio cooperativo Linux não pôde ser obtido.

- Linux: \`flock(fd,LOCK_EX|LOCK_NB)\` (não bloqueia esperando).
  Trata-se de **bloqueio cooperativo**: programas que não respeitam
  \`flock\` podem modificar o arquivo.
- Windows: os recursos RS abrem arquivos com \`dwShareMode=0\` em
  \`CreateFileA\`, impedindo acessos compartilhados compatíveis.
  \`bloqueie_arquivo\` confirma o recurso já aberto; exclusão é
  estabelecida na **abertura**, não por \`LockFileEx\` separado.
- Fechar o arquivo libera o bloqueio/compartilhamento.

Bloquear o arquivo provisório não impede escritores independentes
de disputar **outro** nome provisório ou a versão publicada.
Aplicações multi-processo devem ter estratégia explícita de
arbitragem, como um arquivo de controle comum que todos respeitam.

## 4. Caminhos de arquivo variáveis

A assinatura anterior de \`abra_arquivo\` com literal não foi removida.
Agora o primeiro argumento aceita também **\`texto[N]\`**:

\`\`\`text
inicio {
    seja nome: texto[64]
    copie(nome, "dados_2026.rsd")
    seja arq: arquivo
    seja estado = 0
    abra_arquivo(nome, arq, "novo", estado)
    escreva(estado)
    feche_arquivo(arq, estado)
}
\`\`\`

O compilador gera validação nativa **antes de abrir** o recurso:
comprimento de 1 a 240, basename ASCII composto apenas por letras,
dígitos, sublinhado, ponto e hífen, primeiro caractere restrito a
letra/dígito/sublinhado, proibidos barras, NUL, \`..\` como caminho,
dois-pontos, Unicode e caracteres de controle. No Windows, nomes
reservados como \`CON\`, \`NUL\`, \`PRN\`, \`AUX\`, \`COM1\` e \`LPT9\`
também são recusados, inclusive com extensão. Literais reservados
são recusados na compilação em ambas as plataformas.

Caminhos inválidos devolvem \`-3\` e não abrem recursos. A validação
não é equivalente a sandbox de sistema operacional: o diretório atual
deve ser **confiável**. Não há \`openat2\` com política de resolução
hierárquica nem proteção completa contra links/reparse points e
corridas de nomes. Caminhos parametrizáveis para publicação ainda não
foram introduzidos; permanecem literais para evitar troca entre volumes
ou diretorios não controlados.

## 5. Estados tipados

A biblioteca \`importe "padrao/arquivos.rts"\` oferece
\`resultado_arquivo(estado)\` para converter códigos nativos:

| Código | Significado |
|---|---|
| 1 a 6 | Erros já estabelecidos na RS 0.38 |
| 7 | Bloqueio não adquirido (\`-7\`) |
| 8 | Falha na publicação (\`-8\`) |
| 9 | Falha ao sincronizar o diretório (\`-9\`) |
| 10 | Erro nativo desconhecido (antes era 7) |

A mudança de 7 para 10 no código de erro **desconhecido** altera o
contrato experimental do adaptador; testes de compatibilidade foram
atualizados para explicitar essa mudança.

## 6. Testes e próximos marcos

\`testes/test_publicacao_rs039.py\` executa os binários gerados pela
RS em Windows/Linux e verifica: troca completa de arquivo, alteração
da versão anterior, origem provisória ausente, falha injetada antes da
troca, falha depois da troca, nomes variáveis válidos/inválidos,
limites de comprimento, dispositivos reservados Windows e \`flock\`
contendido no Linux. Os níveis \`-O 0\` a \`-O 8\` são exercitados.

A próxima evolução deve enfrentar sincronização sob falhas injetadas
de chamadas de sistema, acesso concorrente controlado à versão
publicada, identificadores de caminho estáveis, arquivo de controle,
formato versionado e recuperação. **O Dados RS continua separado.**
