## MODIFIED Requirements

### Requirement: Status bar v3 — esquerda limpa, direita informativa

O `status-left` SHALL exibir apenas o indicador de modo tmux (KEY/COPY/INPUT via condicional `#{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}}`) e o nome da sessão (`#{session_name}`), substituindo o formato anterior que incluía `#S:#W` e a lista de janelas. **Nota:** `#{tmux_mode_Indicator}` não é um formato tmux válido (testado na versão 3.4); usou-se o condicional equivalente que funciona em tmux 3.2+. O `status-right` SHALL exibir o agente da janela ativa (`#{@agent}`), a versão do SAC, o resumo de agentes (`sac status --mini`) e a data no formato `dd/MM dow HH:MM`.

#### Scenario: Status bar v3 após `sac up`
- **GIVEN** sessão SAC no ar com workspace "Github"
- **WHEN** `sac up` termina
- **THEN** `status-left` contém o condicional `#{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}}` e `#{session_name}` e NÃO contém `#S:#W` nem lista numerada de janelas
- **AND** `status-right` contém `#{@agent}`, `SAC <versão>`, `#(sac status --mini` e `#(date +"%d/%m %a %H:%M")`
- **AND** `status-right` NÃO contém dicas estáticas (`MouseDrag`, `S-C-v`, `C-b o`)

#### Scenario: Formato da data no padrão brasileiro
- **GIVEN** sábado, 25 de julho de 2026, 19:58
- **WHEN** `date +"%d/%m %a %H:%M"` é executado
- **THEN** a saída é `25/07 sáb 19:58`

### Requirement: Pane-border-format com identidade de agente

Todo pane de harness SHALL exibir o nome do agente na moldura superior via `pane-border-format="#{@agent}"`. A cor da borda SHALL ser determinada por hash do nome do agente (estável por sessão). O pane ativo SHALL ter realce visual distinto. A sidebar SHALL manter `pane-border-format=""` (sem borda nomeada).

#### Scenario: Pane de harness exibe nome do agente na moldura
- **GIVEN** sessão SAC no ar com agente `leader` (kimi)
- **WHEN** `sac up` conclui a configuração dos panes
- **THEN** o `pane-border-format` do pane do `leader` contém `#{@agent}`
- **AND** a moldura renderiza "leader" na borda superior

#### Scenario: Cor da borda estável por hash
- **GIVEN** agente `code-auditor` com hash do nome em 0x1A2B
- **WHEN** a cor da borda é calculada via `hash(name) % len(palette)`
- **THEN** a cor selecionada é a mesma em múltiplas execuções
- **AND** agentes diferentes provavelmente têm cores diferentes

#### Scenario: Pane ativo realçado via after-select-pane hook
- **GIVEN** janela com agente `leader` (foco) e `dev-1` (sem foco)
- **WHEN** o foco muda para `dev-1`
- **THEN** o hook `after-select-pane` executa: todos os panes recebem `pane-border-style fg=colour240`
- **AND** o pane ativo (`dev-1`) recebe `pane-border-style fg=#{@agent_color}` para realce pela cor do agente
- **AND** o pane inativo (`leader`) mantém `pane-border-style fg=colour240`

#### Scenario: Sidebar sem borda de agente
- **GIVEN** pane da sidebar com `@pane_role=sidebar`
- **WHEN** a moldura é configurada
- **THEN** `pane-border-format=""` é aplicado (borda vazia)

### Requirement: Window options globais ao servidor tmux dedicado

`pane-border-status`, `pane-border-lines`, `window-status-format` e `window-status-current-format` SHALL ser aplicadas com `-g` (server-global) no socket tmux dedicado. Aplicar com `-t <sessão>` afetaria apenas a janela corrente — os demais panes do harness ficariam sem borda superior e sem formatação de janela.

#### Scenario: Opções de janela aplicadas globalmente
- **GIVEN** sessão SAC ativa com múltiplas janelas de harness
- **WHEN** `_configure_appearance` executa
- **THEN** `pane-border-status top` e `pane-border-lines heavy` são aplicados com `-g` (set-option global)
- **AND** `window-status-format ""` e `window-status-current-format ""` são aplicados com `-g`
- **AND** todas as janelas do servidor refletem as opções, não apenas a corrente
