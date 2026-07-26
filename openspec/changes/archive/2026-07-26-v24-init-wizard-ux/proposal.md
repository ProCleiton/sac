# Proposal — v24-init-wizard-ux

## Por quê

Teste real do `sac init` (26/07, workspace NFI) mostrou que o wizard da v22
ainda exige demais do usuário iniciante: hints sem exemplos concretos, papel do
agente 1 (leader/orquestrador) não anunciado, default de harness que parece
detecção mas é placeholder, pergunta inútil de "Papel (leader/aux)", nenhuma
ajuda para montar os contratos de prompt (`prompt_file`) nem o layout
`[windows]`, config `sac.toml` poluindo a raiz do workspace e nenhum caminho
para "começar do zero". Decisão do usuário: o usuário é preguiçoso — **o wizard
tem que ser auto-suficiente, sem ida ao repositório para aprender a configurar**.

Decisão de produto registrada: **superpowers (plugin de skills dos harnesses) e
OpenSpec (CLI) são a stack canônica do SAC**. Os contratos canônicos embutidos
no SAC traduzem essas disciplinas para texto; o wizard injeta o contrato certo
automaticamente a partir do papel escolhido, e o usuário pode editar
`prompts/<nome>.md` depois, se quiser.

## O que muda

1. **Wizard reescrito para "zero ida ao repo"**
   - Abertura explicando o que será gerado e onde.
   - Hints com exemplos concretos em todas as perguntas (sessão, socket,
     boot_wait global e específico).
   - Agente 1 anunciado como leader/orquestrador (header + hint explicando o
     que o leader faz).
   - Pergunta "Papel (leader/aux)" eliminada — agentes 2+ são `aux`
     automaticamente.
   - Default inteligente de harness: detecta no PATH (kimi → opencode →
     claude) e oferece o encontrado como default; sem nenhum, cai no
     placeholder atual. Validação com warning da v22 é mantida.
2. **Catálogo de contratos canônicos** — por agente, uma pergunta numerada
   (líder, desenvolvedor, revisor, documentação, deploy/release, segurança,
   auxiliar genérico); o contrato completo é escrito automaticamente em
   `prompts/<nome>.md`. Contratos inspirados nas disciplinas do superpowers
   (TDD, debugging sistemático, revisão por evidência) e no workflow OpenSpec,
   funcionando sem o plugin instalado. Default: líder para o agente 1 (sem
   pergunta), desenvolvedor para os demais.
3. **Agrupamento manual de janelas `[windows]`** — pergunta s/N; se sim, por
   janela: nome, agentes (validados contra os criados) e disposição
   (`;` colunas / `,` pilha), com preview antes de confirmar.
4. **Config oculto com fallback** — init escreve `.sac/sac.toml`. Descoberta:
   `--config` → `$SAC_CONFIG` → `./.sac/sac.toml` → `./sac.toml` (fallback,
   esteiras antigas seguem funcionando). `doctor` reporta qual arquivo usou e
   avisa se ambos existirem.
5. **`sac uninstall`** — recusa se a sessão tmux estiver no ar ("rode
   `sac down` antes"); lista o que será removido (`.sac/`, `prompts/`,
   `sac.toml` legado se existir); exige digitar o nome da sessão para
   confirmar. Não toca em nada fora do workspace.
6. **`doctor` e stack canônica** — novo item WARN para o CLI `openspec` no
   PATH; README ganha seção sobre a stack canônica (superpowers + OpenSpec).

## Non-goals

- Migração automática de esteiras existentes para `.sac/sac.toml` (o fallback
  as mantém funcionando; migrar é manual e opcional).
- Gramática aninhada de `[windows]` (backlog conhecido).
- Editor de contrato dentro do wizard (editar = abrir o arquivo gerado).
- Instalar plugin superpowers ou CLI openspec (domínio do usuário; o doctor só
  detecta e orienta).

## Specs afetadas

- `cli` (MODIFIED: init, doctor, geração de config; ADDED: uninstall,
  descoberta de config com fallback)
- `config` (MODIFIED: geração de sac.toml via template — caminho `.sac/sac.toml`)

## Riscos

- Mudança de caminho do config é o ponto mais sensível: mitigada pela ordem de
  descoberta com fallback e por testes de precedência.
- Wizard maior = mais código interativo: mitigado por FakeInput nos testes e
  por manter cada pergunta em função isolada.
