# Design — v18-sidebar-rodape-v2

## Contexto

v17 entregou sidebar v2 (tree/comms/tips) e status bar v1. Esta iteração
fecha a paridade com o CCB: divisão visual de subníveis na árvore, modelo por
agente, badges/contadores, tempo ocioso, e rodapé sem dicas estáticas com
sessão/window e resumo de agentes.

## Decisões

- **Modelo vem de `args`**: `AgentConfig` não tem campo `model` — o modelo é
  extraído de `--model <valor>` em `args` (`_agent_model`), com basename do
  comando (`/usr/bin/kimi` → `kimi`) e sem o alias (`esteira/k3` → `k3`).
  Formato exibido: `comando/modelo`; sem `--model`, só o comando. Nenhuma
  mudança de schema na config (compatibilidade total).
- **Badge e idade são leituras novas do Store** (`inbox_count`,
  `last_event_age`) — filesystem puro, sem estado novo. Idade formatada por
  `_fmt_age` (`5m`/`1h`/`2d`), omitida para agentes sem eventos.
- **Conectores `├─`/`└─`** calculados pelo índice do agente na window
  (último → `└─`). Foco (`*`) move-se para depois do conector.
- **Resumo no rodapé via `#(sac status --mini)`**: o tmux executa o comando a
  cada `status-interval` no cwd da sessão (que é o project root com
  `sac.toml`). `--mini` nunca falha: sem store/config imprime linha vazia e
  retorna 0; `2>/dev/null` no formato protege o resto. Formato `<n>● <n>!`,
  contadores zerados omitidos.
- **Truncamento por largura visível** (`_truncate_ansi`): linhas da sidebar
  são cortadas na largura do terminal preservando ANSI (com reset ao cortar).
  Motivo: linha maior que o pane quebra o redraw in-place do `--watch`
  (wrap desloca todas as linhas seguintes — achado na validação ao vivo).
- **Frame do `--watch` limpa linha a linha** (`_frame`: `\033[H` + `\033[K`
  por linha + `\033[J`): sem isso, frames novos com linhas mais curtas
  deixavam restos do frame anterior (achado na validação ao vivo da v18,
  corrigindo defeito da v17).
- **Identidade do agente via `@agent` pane option, NUNCA `pane_title`**: o
  kimi troca o título do pane para "Kimi Code" segundos após o boot
  (reproduzido ao vivo), o que dissolvia a árvore da sidebar no refresh
  seguinte. `sac up` grava `@agent=<nome>` em todo pane de harness (grid e
  legado); sidebar e status bar (`#{?#{@agent},#{@agent},#{pane_title}}`)
  leem `@agent`.

## Alternativas descartadas

- Campo `model` na config: mudança de schema desnecessária — `args` já carrega
  a informação.
- TUI interativo (curses/textual) para a sidebar: overkill; o render ANSI
  atual + `--watch` já atende.

## Testes

- Store: `inbox_count` (0/2/após next), `last_event_age` (None sem log, idade
  em segundos, agente sem eventos).
- Sidebar v3: conectores (2 agentes + agente único), modelo com/sem `--model`
  e com path, badge `(N)`, idade `· 5m`, ausência de idade sem eventos,
  truncamento na largura, frame com `\033[K` por linha.
- CLI: `status --mini` com contadores, vazio, sem store.
- Status bar: `status-right` sem `MouseDrag`/`S-C-v`, com `#S:#W` e
  `sac status --mini`.
- Ao vivo: sessão de teste com harness fake — sidebar e rodapé conferidos com
  `capture-pane` (árvore, badge, idade, comms, tips sem artefatos).
