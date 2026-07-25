## Context

O SAC replica o layout do CCB (`materialize_topology.py` + `topology_plan.py`
+ `tmux_theme.py` do pacote `@seemseam/ccb`), adaptado às restrições do
projeto: **Python stdlib only**, sidebar textual renderizada em loop (sem
ratatui/Rust), tmux dirigido por wrappers em `sac/tmux.py` com `FakeRunner`
nos testes.

## Goals / Non-Goals

- Goals: gramática `[windows]` `;`/`,`; grid recursivo; sidebar v2
  (tree/comms/tips); bordas com cor estável; status bar; compat total sem
  `[windows]`.
- Non-Goals: parênteses/grupos aninhados e `@N` (percentual explícito) na
  gramática (v2 futura); profiles de tema; sidebar interativa (teclas/mouse);
  pane `cmd` genérico; migração do daemon para fora da window `dash`.

## Decisions

### D0 — Referências de layout: CCB + tmux-agent-sidebar
Duas fontes estudadas: o CCB instalado (`@seemseam/ccb`, layout de windows em
grid) e o `hiroppy/tmux-agent-sidebar` (sidebar universal para panes de
agentes). Do segundo, as ideias adotadas nesta change: **pane options
`@pane_role=sidebar` como marcação/identidade** (o servidor tmux vira o
barramento de estado — sem IPC própria), **toggle da sidebar por
split-window** (equivalente ao `prefix+e` deles) e a **escala de prioridade
de status** (`running > permission > background > waiting > idle`) adaptada
à semântica da fila SAC. **Descartado (decisão do usuário, 25/07)**: hooks
dos harnesses para wait-reasons finos — o SAC é coordenador com protocolo
próprio (claimed/done/escalação), não espião passivo de harnesses; os estados
que os hooks detectariam já são cobertos pelo protocolo (travou → reporte ao
líder + escalonamento do daemon). Adiados para v18 (fora de escopo):
notificações desktop com dedup por fingerprint, spawn/teardown de worktrees,
tabs interativas Activity/Git e refresh por SIGUSR1.

### D1 — Gramática v1: flat, sem grupos
`;` separa colunas (split right), `,` empilha dentro da coluna (split bottom).
Sem `(...)` nem `@N` — percentuais automáticos proporcionais ao número de
folhas de cada nó (mesma regra do CCB em `_materialize_layout`). Precedência:
`,` liga mais forte que `;` — `"a,b;c"` = coluna [a sobre b] ao lado de [c].
Alternativa rejeitada: portar a gramática completa com grupos — complexidade
sem uso real no SAC (3-8 agentes).

### D2 — Sidebar: 15% com piso de 28 colunas
CCB usa 15% fixo; o SAC atual usa 30 colunas fixas. Adotar 15% da largura da
window com mínimo de 28 colunas (tree legível em terminais estreitos).
O hook `client-resized` reaplica o valor — agora calculado por window (cada
window pode ter largura diferente após resize manual), não mais constante
global `SIDEBAR_WIDTH`.

### D3 — Sidebar v2 textual (sem TUI interativa), com toggle e identidade por pane option
Uma instância de `sac sidebar` por window (loop `clear; sac sidebar; sleep 5`,
como hoje). O pane da sidebar é marcado com `tmux set-option -p
@pane_role=sidebar` (padrão do tmux-agent-sidebar): permite ao toggle e ao
hook de resize localizar a sidebar sem heurística de `pane_start_command`.
Toggle: `sac sidebar --toggle` (mata o pane `@pane_role=sidebar` da window
corrente ou o cria com split à esquerda, 15%), com bind `prefix + e`
configurado no `up` — espelho do `prefix+e` do tmux-agent-sidebar.
Conteúdo em texto plano com marcadores unicode:
```
> main          ← window ativa
  leader  ● [kimi]
  trabalho
  dev-1   ◐ [opencode]
  auditor · [kimi]

comms
23:36 daemon→leader escalate dev-1
23:34 dev-1→leader PONG2

tips
C-b h/j/k/l pane   C-b o next
C-b H/J/K/L resize C-b z zoom
C-b w tree         C-b [ copy
```
Atividade segue a escala de prioridade adaptada (D0): `●` = claimed>0
(running), `!` = escalado/poke≥N (atenção — análogo ao permission/waiting de
permissão), `◐` = inbox>0 (waiting), `·` = ocioso (idle); `*` = pane focado
(via `list-panes -F '#{pane_active}'`). Comms: últimos 5 eventos do
`log.jsonl` (linha única compactada `HH:MM sender→to evento`). Alternativa
rejeitada: portar o sidebar Rust do CCB ou a TUI ratatui do
tmux-agent-sidebar — foge do stdlib-only; tabs interativas ficam para a v18.

### D4 — Cor estável por agente
`cor = PALETA[sha256(agent.name) % 8]`, paleta fixa de 8 cores ansi256
(ex.: 203, 215, 114, 39, 75, 141, 176, 180). Aplicada em
`pane-border-style` por pane + `pane-border-status top` com o nome do agente.
Pane ativo: borda `heavy` + cor; inativo: `colour240`. Realce via hook
`after-select-pane` (reaplica os estilos — mesmo mecanismo do `ccb-border.sh`).

### D5 — Status bar única (sem profiles)
```
[KEY] main ⎇  sac                           leader  SAC 1.6  25/07 14:07
```
Esquerda: segmento de modo (`#{?client_prefix,KEY,··}` / COPY via
`#{pane_in_mode}`) + branch git do `project_root` (`git branch --show-current`
resolvido no `up`, estático). Direita: agente do pane ativo
(`#{pane_title}`), `SAC <versão>`, data. `window-status-format` vazio (a tree
da sidebar substitui a lista de windows — como no CCB).

### D6 — dash preservada, entry window = primeira do [windows]
A window `dash` (daemon + `sac log -f`) continua sendo criada por último.
Select/attach cai na primeira window declarada em `[windows]` (default de
fato: a que contém o leader). Sem `[windows]`: comportamento idêntico ao
atual (1 window/agente + dash, select no leader).

### D7 — Plano separado da materialização
`sac/layout.py`: `parse_spec("a,b;c") -> Node` (Col | Row | Leaf) e
`build_plan(cfg) -> list[WindowPlan]` (window → árvore + percentuais
resolvidos). `cmd_up` consome o plano com chamadas tmux já existentes
(`new_window`, `split_window`, `resize_pane`). Testável com `FakeRunner` sem
tmux real (asserção na sequência de splits e percentuais).

## Risks / Trade-offs

- **Splits recursivos com percentuais**: tmux aceita `-p` no split-window;
  erro de arredondamento em grids grandes → mitigar aplicando percentual
  relativo ao espaço restante (regra do CCB) e testar 1..4 folhas.
- **Hook `client-resized` atual assume 1 window/agente** → reescrito para
  iterar windows do plano; risco de regressão no layout legado → teste de
  integração cobre os dois modos.
- **Sidebar v2 quebra scripts que parseiam o formato antigo?** Não há
  consumidores programáticos do `sac sidebar` (saída para humanos) — seguro.
