## MODIFIED Requirements

### Requirement: Materialização do grid no boot

O sistema SHALL, quando `[windows]` estiver presente, criar cada window com
uma sidebar à esquerda (18% da largura, mínimo 28 colunas) e os panes de
agentes conforme o plano, usando os wrappers tmux existentes.

#### Scenario: Boot com grid 2x1
- **GIVEN** `[windows]` com `main = "leader"` e `trabalho = "dev-1,auditor"`
- **WHEN** `sac up` executa
- **THEN** a window `trabalho` tem sidebar à esquerda + dev-1 sobre auditor
- **AND** cada pane de harness recebe `SAC_AGENT` e título do agente
- **AND** a window `dash` (daemon + log) é criada por último
- **AND** o select final cai na primeira window declarada (`main`)

#### Scenario: Boot sem [windows] preserva layout legado
- **GIVEN** config sem seção `[windows]`
- **WHEN** `sac up` executa
- **THEN** o layout atual (1 window por agente + dash, select no leader) é
  reproduzido sem alteração

### Requirement: Sidebar global com tree, comms e tips

O sistema SHALL renderizar no `sac sidebar` três seções: árvore de windows e
agentes com indicadores (sem modelo AI — apenas harness), últimos eventos de
mensageria e atalhos tmux. O conteúdo SHALL ser truncado (NÃO wrapping) quando
exceder a largura do terminal. As caixas das seções SHALL usar padding fixo 23.
A seção tips SHALL exibir um atalho por linha (indent 2 espaços), sem barra de
rolagem.

#### Scenario: Tree com indicadores de atividade
- **WHEN** a sidebar renderiza
- **THEN** a window ativa aparece com `>`; cada agente com `●` (claimed),
  `!` (escalado pelo daemon), `◐` (inbox pendente) ou `·` (ocioso), mais o
  harness command em cinza (ex.: `kimi`); o agente focado recebe `*`
- **AND** NÃO contém o modelo AI (--model) — apenas o harness command

#### Scenario: Comms com últimos eventos
- **GIVEN** log.jsonl com eventos recentes
- **WHEN** a sidebar renderiza
- **THEN** os últimos 5 eventos aparecem como `HH:MM sender→to evento`

#### Scenario: Tips com atalhos fixos
- **WHEN** a sidebar renderiza
- **THEN** a seção tips lista os atalhos tmux (navegação de pane, resize,
  zoom, tree, copy-mode, paste, detach)
- **AND** cada atalho aparece em linha própria com indentação 2 espaços
- **AND** NÃO há trilho, polegar ou qualquer elemento de scrollbar

#### Scenario: Padding fixo 23 nas caixas
- **GIVEN** sidebar com qualquer largura >= 28 colunas
- **WHEN** `_section("comms")` ou `_section("tips")` é chamado
- **THEN** a linha renderizada tem padding `23` (ex.: `╭─ comms ───────────────────╮`)
- **AND** a linha nunca ultrapassa a largura da sidebar

#### Scenario: Linha longa é truncada (NÃO wrap)
- **GIVEN** linha de árvore ou conteúdo que excede a largura do terminal
- **WHEN** a sidebar renderiza
- **THEN** a linha é cortada na largura visível com reset ANSI ao final

### Requirement: Toggle e identidade da sidebar

O sistema SHALL marcar o pane da sidebar com a pane option
`@pane_role=sidebar` e SHALL oferecer toggle da sidebar na window corrente
(`sac sidebar --toggle` + bind `prefix + e`), criando o pane com split à
esquerda quando ausente e matando-o quando presente.

#### Scenario: Toggle cria sidebar ausente
- **GIVEN** uma window sem pane `@pane_role=sidebar`
- **WHEN** roda-se `sac sidebar --toggle` (ou `prefix + e`)
- **THEN** um split à esquerda (18%, piso 28 col) é criado rodando a sidebar
- **AND** o pane é marcado com `@pane_role=sidebar`
- **AND** o foco volta ao pane original

#### Scenario: Toggle remove sidebar presente
- **GIVEN** uma window com pane `@pane_role=sidebar`
- **WHEN** roda-se `sac sidebar --toggle`
- **THEN** o pane da sidebar é morto

#### Scenario: Bind prefix+e configurado no up
- **WHEN** `sac up` executa
- **THEN** a sessão tem bind `e` para `sac sidebar --toggle` na window
  corrente

### Requirement: Status bar com modo, git e agente focado

O sistema SHALL configurar a status line da sessão com a paleta Catppuccin
Mocha e segmentos powerline (U+E0B0/U+E0B2). Esquerda: segmento de modo
(KEY/COPY/INPUT) com bg dinâmico via condicional tmux (pink/red/peach) →
U+E0B0 → workspace name (basename do project_root) centralizado em cinza
`#6c7086` — sem session_name nem mauve. Direita: worker `#{@agent}` red →
U+E0B2 → `#(sac --version 2>/dev/null)` mauve → U+E0B2 →
`#(sac status --mini)` blue → U+E0B2 → `#(date +"%d/%m %a %H:%M")` peach.
`status-style bg=#1e1e2e,fg=#cdd6f4`. `status-left-length=80`,
`status-right-length=120`.

#### Scenario: Status bar configurada no up
- **WHEN** `sac up` executa
- **THEN** a status line mostra o modo e o workspace (sem session_name) à esquerda
- **AND** mostra agente, versão dinâmica, resumo de agentes e data à direita
- **AND** `window-status-format` fica vazio (a tree da sidebar substitui a lista de windows)
- **AND** `status-style bg=#1e1e2e,fg=#cdd6f4`
- **AND** `status-left-length=80`, `status-right-length=120`
