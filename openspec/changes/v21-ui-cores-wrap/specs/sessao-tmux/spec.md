## MODIFIED Requirements

> **Nota:** Esta change MODIFICA a requirement "Status bar v3" do spec master (substitui cores genéricas colour213/203/215 pelo esquema powerline Catppuccin da v4) e a sub-requirement "Sidebar sem borda de agente" (da requirement "Pane-border-format com identidade de agente", v20) — a sidebar agora exibe label "sidebar" (fg=colour245) no pane-border-format, a pedido do usuário. Após archive, o spec master refletirá ambas.

### Requirement: Status bar v4 — paleta e segmentos CCB powerline (substitui "Status bar v3")

O `status-left` e `status-right` SHALL usar o esquema de cores Catppuccin Mocha e segmentos powerline do CCB, mantendo o CONTEÚDO informativo da v20. A paleta SHALL ser: background `#1e1e2e`, texto `#cdd6f4`, cinza overlay `#6c7086`, modo com cor dinâmica (pink `#f5c2e7` padrão, red `#f38ba8` em client-prefix, peach `#fab387` em copy-mode), agente red `#f38ba8`, versão mauve `#cba6f7`, indicador blue `#89b4fa`, data peach `#fab387`. **Nota:** a paleta de referência está em `terminal_runtime/tmux_theme.py` do CCB (`_DARK_STATUS`).

O `status-left` SHALL conter: segmento de modo (INPUT/KEY/COPY) com cor dinâmica via condicional tmux DENTRO do atributo `fg` (ramos com cores nuas, sem vírgula), seguido de powerline right-triangle U+E0B0 na cor do modo para fundo base `#1e1e2e`; depois `#[align=centre]` com o NOME DO WORKSPACE (basename do `project_root`, estático no `up`) em cinza `#6c7086`; depois `#[align=left]`. NÃO deve conter `session_name`, nem bloco mauve.

O `status-right` SHALL conter segmentos powerline left-triangle U+E0B2: `[worker #{@agent} red bold]` → U+E0B2 → `[#(sac --version 2>/dev/null) mauve bold]` → U+E0B2 → `[#(sac status --mini) blue]` → U+E0B2 → `[#(date +"%d/%m %a %H:%M") peach bold]`. Todos os textos dos segmentos em fg `#1e1e2e`. O segmento de versão é dinâmico (`#()`), resolvido pelo tmux a cada render — sessões antigas sempre mostram a versão atual do código SAC.

`status-style` SHALL ser `bg=#1e1e2e,fg=#cdd6f4`. `status-left-length` = 80, `status-right-length` = 120.

#### Scenario: Status bar v4 após `sac up` — left side
- **GIVEN** sessão SAC no ar com workspace "Github"
- **WHEN** `sac up` termina
- **THEN** `status-left` contém segmento de modo com bg dinâmico (pink/red/peach) e texto `KEY`/`COPY`/`INPUT` em bold, fg `#1e1e2e`
- **AND** a condicional tmux para a cor do modo usa ramos dentro do atributo `fg` com cores nuas (ex.: `#{?client_prefix,#f38ba8,#{?pane_in_mode,#fab387,#f5c2e7}}`)
- **AND** powerline triangle U+E0B0 (`#[fg=<cor_do_modo>,bg=#1e1e2e]\ue0b0`) transiciona do modo para o fundo base
- **AND** `#[align=centre]` posiciona o nome do workspace ao centro
- **AND** o nome do workspace ("Github") aparece em cinza `#6c7086`
- **AND** `#[align=left]` retorna o alinhamento à esquerda
- **AND** `status-left` NÃO contém `#S:#W` nem `session_name` nem bloco mauve

#### Scenario: Status bar v4 — right side
- **GIVEN** sessão SAC no ar com agente `leader` na janela ativa
- **WHEN** `sac up` termina
- **THEN** `status-right` contém: worker `#{@agent}` com bg red `#f38ba8`; U+E0B2 (`#[fg=#cba6f7,bg=#f38ba8]\ue0b2`); `#(sac --version 2>/dev/null)` com bg mauve `#cba6f7`; U+E0B2 (`#[fg=#89b4fa,bg=#cba6f7]\ue0b2`); `#(sac status --mini)` com bg blue `#89b4fa`; U+E0B2 (`#[fg=#fab387,bg=#89b4fa]\ue0b2`); data `#(date +"%d/%m %a %H:%M")` com bg peach `#fab387`
- **AND** todos os textos dos segmentos em fg `#1e1e2e` (base escuro sobre fundo claro)
- **AND** NÃO contém dicas estáticas (`MouseDrag`, `S-C-v`, `C-b o`)
- **AND** `status-right-length` = 120

#### Scenario: Versão dinâmica — `#(sac --version 2>/dev/null)`
- **GIVEN** sessão SAC no ar
- **WHEN** `sac up` termina
- **THEN** o segmento de versão no `status-right` usa `#(sac --version 2>/dev/null)` com bg mauve `#cba6f7`
- **AND** o tmux reevaluates o comando a cada render (não é string fixa do `up`)
- **AND** o flag `--version` na CLI usa `importlib.metadata.version("sac")`
- **AND** sessões antigas mostram a versão atual do código SAC sem precisar de `sac up`

#### Scenario: Cores fixas independente de tema do terminal
- **GIVEN** tema claro do terminal
- **WHEN** a status bar é renderizada
- **THEN** a paleta fixa Catppuccin Mocha continua sendo usada (não há detecção de tema)
- **AND** o contraste entre fg `#1e1e2e` e os fundos coloridos é suficiente para leitura

#### Scenario: status-style e tamanhos
- **GIVEN** sessão SAC no ar
- **WHEN** `sac up` termina
- **THEN** `status-style` está configurado como `bg=#1e1e2e,fg=#cdd6f4`
- **AND** `status-left-length` = 80
- **AND** `status-right-length` = 120

### Requirement: Sidebar com label "sidebar" no pane-border-format (substitui "Sidebar sem borda de agente" da v20)

O `pane-border-format` do pane da sidebar SHALL exibir o label fixo `sidebar` (fg=colour245, cinza), revertendo a decisão da v20 de mantê-lo vazio. Harnesses continuam exibindo `#{@agent}` com cor por hash. **Motivação:** o usuário solicitou o label durante a homologação da v21 para identificar visualmente o pane da sidebar.

#### Scenario: Sidebar exibe label "sidebar" no pane-border-format
- **GIVEN** pane da sidebar com `@pane_role=sidebar`
- **WHEN** `_mark_sidebar_pane` é executado
- **THEN** `pane-border-format` do pane da sidebar contém a string ` sidebar ` com `fg=colour245`
- **AND** harnesses continuam com `pane-border-format` contendo `#{@agent}` e cor por hash
