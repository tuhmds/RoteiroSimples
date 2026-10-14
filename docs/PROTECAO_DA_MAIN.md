# Proteção da ramificação principal da RS

Este guia é para o mantenedor `@tuhmds`. **Objetivo:** receber contribuições por *fork* e *pull request*, com incorporação de mudanças somente depois de revisão autorizada.

## O que um fork permite

Em um repositório **público**, qualquer pessoa pode criar um fork, trabalhar nele e enviar uma PR ao repositório original **sem acesso de escrita** no original. Não é necessário convidá-la como colaboradora para que envie PRs. Assim, o primeiro controle é **não conceder acesso de escrita** a quem só precisa contribuir.

## Ordem segura de ativação

1. Verifique se a **PR de preparação da documentação e do CODEOWNERS** já foi revisada e incorporada à `main`. Sem isso, a proteção de revisão por proprietário não reconhece o arquivo que está apenas em uma ramificação de trabalho.
2. Revise arquivos e **histórico de commits** antes de publicar: a alteração de visibilidade também expõe versões históricas do código. Procure credenciais, chaves, dados privados e artefatos indevidos. Se houver segredo, revogue-o/rotacione-o antes; apagar o arquivo da versão atual não elimina o histórico.
3. Decida e documente uma **licença de software**, conforme sua intenção de autorizar ou não a reutilização. Tornar o repositório público **não é o mesmo que conceder uma licença de código aberto**.
4. No GitHub, altere a visibilidade para **Public** em `Settings → General → Danger Zone → Change repository visibility`.
5. Vá a `Settings → Branches → Add branch protection rule` (ou `Settings → Rules → Rulesets`) e proteja exatamente a ramificação `main`.
6. Verifique que a regra está **ativa** e revise o comportamento numa PR de teste feita a partir de um fork.

## Configuração recomendada da main

| Configuração | Valor |
| --- | --- |
| Padrão / alvo | `main` |
| Require a pull request before merging | **Ativar** |
| Require approvals | **Ativar, 1 aprovação** |
| Require review from Code Owners | **Ativar** (com `.github/CODEOWNERS` na `main`) |
| Dismiss stale pull request approvals | **Ativar** |
| Require status checks to pass before merging | **Ativar**, selecionando verificações reais do fluxo `Testes RS` |
| Require conversation resolution before merging | **Ativar** |
| Allow force pushes | **Desativar** |
| Allow deletions | **Desativar** |

A integração contínua está em [`.github/workflows/testes.yml`](../.github/workflows/testes.yml). Ela executa testes do compilador em Windows/Linux numa matriz de versões de Python. Na tela da proteção, use os **nomes de verificações efetivamente registrados pelo GitHub** e confira que foram executados em uma PR recente; não adivinhe nomes de jobs nem estabeleça verificações inexistentes.

### Atenção a suas próprias PRs

O GitHub não permite ao autor contar a **própria aprovação** da sua PR. Portanto, se você for o único revisor com permissão de escrita e ativar **Do not allow bypassing the above settings**, poderá ficar impossibilitado de incorporar suas próprias PRs. Se quiser exigir revisão também para seus próprios commits, tenha **outro revisor de confiança** com acesso apropriado.

Para preservar a decisão final do proprietário sem exigir outro revisor agora, mantenha a possibilidade de *bypass* apenas ao administrador da conta, com responsabilidade: isso significa que tecnicamente **você mesmo** pode pular uma regra, mas contribuidores externos por fork não podem.

Não conceda acesso `write` ou `admin` a quem só precisa enviar PRs. Os contribuidores externos não devem receber *bypass*. Ao adicionar novos colaboradores com escrita no futuro, revise as exceções à regra.

## Conferência final

- O arquivo `.github/CODEOWNERS` está na `main` e aponta para `@tuhmds`.
- Um usuário externo consegue abrir PR de seu fork, mas **não consegue enviar commit diretamente à `main`**.
- PR sem aprovação ou com testes falhando não é incorporada por um colaborador sem permissão de bypass.
- Após um commit novo numa PR aprovada, a revisão anterior é invalidada, se essa opção estiver ativa.
- Apenas o proprietário decide pela incorporação após a revisão.

Documentação oficial: [Regras de proteção de ramificações](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule), [Revisão por proprietários do código](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).

**Importante:** este documento não ativa a proteção por conta própria. É necessário salvar a regra na interface de administração do repositório.
