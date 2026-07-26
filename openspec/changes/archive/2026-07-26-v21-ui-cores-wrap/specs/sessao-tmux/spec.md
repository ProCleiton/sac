## MODIFIED Requirements

### Requirement: Sidebar v3 — árvore com conectores e modelo

A sidebar SHALL renderizar os agentes sob cada window com conectores de árvore
(`├─` para todos exceto o último, `└─` para o último). A árvore SHALL exibir o
harness command (basename do `command`, ex.: `kimi`) como metadado do agente,
mas NÃO o modelo AI (`--model`, ex.: `k3`, `v4`) — o modelo é escolha do
humano no harness; o SAC não o exibe, preservando agnosticidade. A informação
de modelo que o spec master exibia (do `--model` nos args) fica REMOVED.

#### Scenario: Árvore com 2 agentes numa window
- **GIVEN** window `trabalho` com agentes `dev-1` (opencode) e `auditor`
  (kimi, `--model esteira/k3`)
- **WHEN** a sidebar é renderizada
- **THEN** `dev-1` aparece com prefixo `├─` e `auditor` com `└─`
- **AND** `auditor` exibe `kimi` (harness command) e `dev-1` exibe `opencode`
- **AND** NÃO exibe `k3`, `esteira/k3` nem qualquer menção ao `--model`

#### Scenario: Agente único na window
- **GIVEN** window `main` com apenas `leader`
- **WHEN** a sidebar é renderizada
- **THEN** `leader` aparece com prefixo `└─`

### Requirement: Status bar v3 — esquerda limpa, direita informativa

O `status-left` SHALL exibir o indicador de modo tmux (KEY/COPY/INPUT via
condicional DENTRO do atributo `fg`, ramos com cores nuas sem vírgula:
`#{?client_prefix,#f38ba8,#{?pane_in_mode,#fab387,#f5c2e7}}`), seguido de
powerline right-triangle U+E0B0 na cor do modo para fundo base `#1e1e2e`;
depois `#[align=centre]` com o NOME DO WORKSPACE (basename do `project_root`,
estático no `up`) em cinza `#6c7086`; depois `#[align=left]`. NÃO deve conter
`session_name`, nem bloco mauve. Substitui o formato anterior que incluía
`#{session_name}` e condicional simples.

O `status-right` SHALL conter segmentos powerline left-triangle U+E0B2:
worker `#{@agent}` red → U+E0B2 → `#(sac --version 2>/dev/null)` mauve →
U+E0B2 → `#(sac status --mini)` blue → U+E0B2 →
`#(date +"%d/%m %a %H:%M")` peach. Todos os textos dos segmentos em fg
`#1e1e2e`. `status-style` = `bg=#1e1e2e,fg=#cdd6f4`.
`status-left-length` = 80, `status-right-length` = 120.

#### Scenario: Status bar v3 após `sac up`
- **GIVEN** sessão SAC no ar com workspace "Github"
- **WHEN** `sac up` termina
- **THEN** `status-left` contém o condicional com cores nuas e powerline U+E0B0
- **AND** o nome do workspace ("Github") aparece centralizado em cinza `#6c7086`
- **AND** `status-left` NÃO contém `#S:#W` nem `session_name` nem bloco mauve
- **AND** `status-right` contém `#{@agent}`, `#(sac --version 2>/dev/null)`,
  `#(sac status --mini)` e `#(date +"%d/%m %a %H:%M")`
- **AND** `status-right` NÃO contém dicas estáticas (`MouseDrag`, `S-C-v`, `C-b o`)
- **AND** `status-left-length` = 80, `status-right-length` = 120

#### Scenario: Versão dinâmica — `#(sac --version 2>/dev/null)`
- **GIVEN** sessão SAC no ar
- **WHEN** `sac up` termina
- **THEN** o segmento de versão no `status-right` usa `#(sac --version 2>/dev/null)` com bg mauve `#cba6f7`
- **AND** o tmux reevaluates o comando a cada render (não é string fixa do `up`)
- **AND** o flag `--version` na CLI usa `importlib.metadata.version("sac")`
- **AND** sessões antigas mostram a versão atual do código SAC sem precisar de `sac up`

#### Scenario: Formato da data no padrão brasileiro
- **GIVEN** sábado, 25 de julho de 2026, 19:58
- **WHEN** `date +"%d/%m %a %H:%M"` é executado
- **THEN** a saída é `25/07 sáb 19:58`

### Requirement: Pane-border-format com identidade de agente

Todo pane de harness SHALL exibir o nome do agente na moldura superior via
`pane-border-format="#{@agent}"`. A cor da borda SHALL ser determinada por
hash do nome do agente (estável por sessão). O pane ativo SHALL ter realce
visual distinto. A sidebar SHALL exibir o label `sidebar` (fg=colour245,
cinza) no `pane-border-format`, revertendo a decisão anterior de mantê-lo
vazio — a pedido do usuário durante homologação da v21.

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
- **THEN** o hook `after-select-pane` executa: todos os panes recebem
  `pane-border-style fg=colour240`
- **AND** o pane ativo (`dev-1`) recebe `pane-border-style fg=#{@agent_color}`
  para realce pela cor do agente
- **AND** o pane inativo (`leader`) mantém `pane-border-style fg=colour240`

#### Scenario: Sidebar sem borda de agente
- **GIVEN** pane da sidebar com `@pane_role=sidebar`
- **WHEN** `_mark_sidebar_pane` é executado
- **THEN** `pane-border-format` do pane da sidebar contém a string
  ` sidebar ` com `fg=colour245`
- **AND** harnesses continuam com `pane-border-format` contendo `#{@agent}`
  e cor por hash

### Requirement: Persistência da largura da sidebar via hook client-resized

O sistema SHALL manter a largura da sidebar (18%, mínimo 28 colunas) em TODAS
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
