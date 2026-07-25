## Why

O layout atual do SAC (1 window por agente + dash) escala mal: com 3+ agentes,
acompanhar a esteira exige saltar entre windows (C-b n/p/índice) o tempo todo,
e não existe visão única do time. O CCB (gerenciador de harnesses instalado
localmente, mesmo propósito do SAC) resolve isso com um layout comprovado —
analisado no código-fonte (`@seemseam/ccb` em
`~/.nvm/versions/node/v22.11.0/lib/node_modules/`) e no mockup de referência
(`assets/readme_v7/ccb-hero-en-light.png` do repo do CCB):

- **Windows agrupadas por função** (`main`, `coders`, `apoio`, `ops`) com os
  agentes distribuídos em grid de panes dentro de cada window — declaração
  via gramática simples na config (`;` = colunas lado a lado, `,` = empilhado).
- **Sidebar global por window** (~15% à esquerda) com 3 seções: árvore
  windows→agentes com indicadores de atividade, últimas mensagens (Comms) e
  atalhos (Tips).
- **Bordas de pane** com o label do agente e cor estável por agente.
- **Status bar** com modo (KEY/COPY) + branch git à esquerda e agente focado +
  versão + data à direita.

## What Changes

- **Seção `[windows]` no `sac.toml`** (opcional — compatibilidade total: sem
  ela, o layout atual 1-window-por-agente + dash é preservado): cada chave vira
  uma window; o valor é um spec na gramática `;` (split horizontal, colunas) e
  `,` (split vertical, empilhado). Ex.:
  `main = "leader"`, `trabalho = "dev-1,auditor"` (dev-1 em cima, auditor
  embaixo), `apoio = "dev-2;info"` (lado a lado).
- **Materializador de grid**: `cmd_up` constrói as windows do `[windows]` —
  sidebar à esquerda (~15% da largura) e panes de agentes distribuídos
  recursivamente com percentuais proporcionais ao número de folhas. Validação
  no config load: todo agente declarado aparece exatamente 1 vez nos specs;
  spec referenciando agente desconhecido → `ConfigError`.
- **Sidebar v2 (global)**: novo conteúdo do `sac sidebar` em 3 seções —
  **Tree** (windows → agentes; window ativa com `>`; agente com `●` claimed,
  `!` escalado, `◐` inbox pendente, `·` ocioso, `*` focado — escala de
  prioridade inspirada no tmux-agent-sidebar), **Comms** (últimos 5 eventos
  do `log.jsonl`), **Tips** (atalhos tmux fixos). Uma instância por window.
- **Toggle e identidade da sidebar**: pane da sidebar marcado com
  `@pane_role=sidebar` (o tmux vira o barramento de identidade — padrão do
  `hiroppy/tmux-agent-sidebar`); comando `sac sidebar --toggle` (cria/mata o
  pane na window corrente) com bind `prefix + e` configurado no `up`.
- **Bordas de pane com label + cor estável**: `pane-border-status top` com o
  nome do agente; cor escolhida por hash (sha256) do nome dentro de uma paleta
  fixa de 8 cores — o mesmo agente tem sempre a mesma cor.
- **Status bar customizada**: esquerda = indicador de modo (KEY/COPY, muda com
  prefix) + branch git do projeto; direita = agente focado + `SAC <versão>` +
  data/hora. Paleta única (sem profiles de tema).
- **Hooks**: `after-select-pane` (realce da borda do pane ativo) e
  `client-resized` adaptado para manter a largura da sidebar em windows com
  grid (substitui o hook atual, que assume 1 window/agente).
- **Window `dash`**: mantida como última window (daemon + `sac log -f`), com ou
  sem `[windows]`. **Attach/select**: na entry window (primeira do `[windows]`,
  ou leader no layout legado).

## Capabilities

### New Capabilities
- `layout-grid`: seção `[windows]` com gramática `;`/`,`; plano de layout
  (árvore de splits com percentuais); materialização no `cmd_up`; sidebar v2
  (tree/comms/tips); bordas com cor estável por agente; status bar.

### Modified Capabilities
- `config`: parsing e validação da seção `[windows]` (agente desconhecido,
  agente duplicado/ausente nos specs).
- `sessao-tmux`: `cmd_up` materializa o plano de grid quando `[windows]`
  presente; hook de resize adaptado; attach na entry window.

## Impact

**Código**: `sac/config.py` (WindowSpec + validações), novo `sac/layout.py`
(parser da gramática + plano de splits), `sac/commands.py` (`cmd_up`
materialização, `cmd_sidebar` v2), `sac/tmux.py` (helpers: border status,
status bar, hooks). Templates e protocolo de mensageria: intocados.
**Testes**: `tests/test_layout.py` (parser/plano), `tests/test_config.py`
([windows]), `tests/test_commands.py` (up com grid via FakeRunner, sidebar v2),
`tests/test_integration.py` (sessão real com grid 2×1).
Suíte atual: 221 passed → alvo ~250.
