## MODIFIED Requirements

### Requirement: Persistência da largura da sidebar via hook client-resized
O sistema SHALL manter a largura da sidebar (15%, mínimo 28 colunas) em TODAS
as windows com sidebar quando o cliente redimensiona, em vez de assumir 1
window por agente.

#### Scenario: Hook registrado no boot
- **WHEN** `sac up` cria a sessão
- **THEN** um hook é registrado via `tmux set-hook -t <session> client-resized "..."` para re-aplicar resize das sidebars
- **AND** o hook executa `resize-pane` nos panes marcados `@pane_role=sidebar` de todas as windows

#### Scenario: Cliente attach redimensiona — sidebar restaurada
- **GIVEN** sessão ativa com sidebars na largura do plano
- **WHEN** um cliente attach com terminal de largura diferente (evento client-resized)
- **THEN** o hook dispara e re-aplica a largura da sidebar em cada window

#### Scenario: Hook não afeta pane do harness
- **WHEN** o hook client-resized é executado
- **THEN** apenas panes com `@pane_role=sidebar` são redimensionados
- **AND** o pane do harness de cada agente não é alterado

#### Scenario: Resize com layout em grid
- **GIVEN** sessão com `[windows]` (grid) no ar
- **WHEN** o terminal é redimensionado
- **THEN** o hook reaplica a largura da sidebar em cada window do plano

#### Scenario: Resize com layout legado
- **GIVEN** sessão sem `[windows]` no ar
- **WHEN** o terminal é redimensionado
- **THEN** o comportamento atual (sidebar 30 colunas por window de agente) é
  preservado

### Requirement: Aterrissagem no leader
O sistema SHALL selecionar ao final do `sac up` a primeira window declarada
em `[windows]`; sem `[windows]`, mantém o select na window do leader.

#### Scenario: Select inicial
- **WHEN** `sac up` conclui a criação sem `[windows]`
- **THEN** `tmux select-window -t <session>:leader` e `tmux select-pane -t <harness_pane_id>` são executados

#### Scenario: Attach na entry window
- **GIVEN** `[windows]` com `main = "leader"` declarada primeiro
- **WHEN** `sac up` conclui
- **THEN** a window selecionada é `main` e o pane focado é o do leader
