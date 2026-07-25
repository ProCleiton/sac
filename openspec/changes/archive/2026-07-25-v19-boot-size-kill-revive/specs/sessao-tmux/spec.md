# Delta: sessao-tmux

## ADDED Requirements

### Requirement: Sessão criada com tamanho explícito
O sistema SHALL criar a sessão tmux com tamanho explícito (`tmux new-session -d -x <width> -y <height>`), usando os valores de `[session] width`/`height` (default 220x50), para que harnesses bootem com geometria estável independente de cliente attachado. Sessão detached sem tamanho explícito nasce 80x24, o que mata harnesses sensíveis a panes estreitos (ex.: opencode crasha com SIGILL em panes de ~26 col).

#### Scenario: new-session recebe -x/-y
- **WHEN** `sac up` cria a sessão
- **THEN** o comando `tmux new-session -d` inclui `-x <width>` e `-y <height>` da config

#### Scenario: Grid calcula larguras sobre o tamanho configurado
- **GIVEN** layout `[windows]` com gramática lado a lado (`;`)
- **WHEN** a sessão é criada com 220x50
- **THEN** os panes de harness nascem com larguras proporcionais a 220 colunas (ex.: 3 colunas ≈ 70+ col cada)

#### Scenario: Sessão existente não é afetada
- **WHEN** `sac up` encontra sessão já ativa
- **THEN** retorna sem recriar nem redimensionar a sessão existente

### Requirement: Env de sessão exportada aos panes
O sistema SHALL exportar `SAC_ROOT` (raiz do store) e `SAC_CONFIG` (caminho absoluto do sac.toml da sessão) no ambiente de todo pane criado — harnesses (via `sac up` e `sac kill`), sidebars e panes do dashboard — para que comandos `sac` executados nos panes resolvam sempre a sessão correta, independente do cwd do processo.

#### Scenario: Pane de harness recebe env completa
- **WHEN** `sac up` ou `sac kill` cria o pane de um harness
- **THEN** o processo inicia com `SAC_AGENT=<agente>`, `SAC_ROOT=<raiz do store>` e `SAC_CONFIG=<caminho absoluto do config>`

#### Scenario: Panes de sidebar e dashboard recebem env de sessão
- **WHEN** `sac up` cria panes de sidebar ou dashboard (log, daemon)
- **THEN** os processos iniciam com `SAC_ROOT` e `SAC_CONFIG` (sem `SAC_AGENT`)
