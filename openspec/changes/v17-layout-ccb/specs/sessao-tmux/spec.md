## MODIFIED Requirements

### Requirement: Hook de resize da sidebar
O sistema SHALL manter a largura da sidebar (15%, mínimo 28 colunas) em TODAS
as windows com sidebar quando o cliente redimensiona, em vez de assumir 1
window por agente.

#### Scenario: Resize com layout em grid
- **GIVEN** sessão com `[windows]` (grid) no ar
- **WHEN** o terminal é redimensionado
- **THEN** o hook reaplica a largura da sidebar em cada window do plano

#### Scenario: Resize com layout legado
- **GIVEN** sessão sem `[windows]` no ar
- **WHEN** o terminal é redimensionado
- **THEN** o comportamento atual (sidebar 30 colunas por window de agente) é
  preservado

### Requirement: Janela de attach no boot
O sistema SHALL selecionar ao final do `sac up` a primeira window declarada
em `[windows]`; sem `[windows]`, mantém o select na window do leader.

#### Scenario: Attach na entry window
- **GIVEN** `[windows]` com `main = "leader"` declarada primeiro
- **WHEN** `sac up` conclui
- **THEN** a window selecionada é `main` e o pane focado é o do leader
