## Contexto

v18 entregou status bar v2 e sidebar v3; v19 corrigiu boot e revive. Esta iteração fecha a paridade visual com o CCB na status bar e estende a identidade de agente à moldura de todos os panes de harness.

## Decisões

- **`status-left` sem lista de janelas**: usa condicional `#{?client_prefix,KEY,#{?pane_in_mode,COPY,INPUT}}` para o modo atual e `#{session_name}` para o nome da sessão. O formato final inclui fundo colorido por modo (`bg=colour203` para prefix, `bg=colour215` para copy-mode, `bg=colour213` para input) — sem `#S:#W` e sem lista numerada de janelas. O nome da sessão é o workspace (ex.: "Github"), definido pelo usuário no `sac.toml`.
- **`status-right` com data no formato brasileiro**: `date +"%d/%m %a %H:%M"` produz "25/07 sáb 19:58". O tmux não tem formato de data nativo com dia da semana abreviado em português; `#(date ...)` dentro do format string resolve.
- **Cor da moldura por hash do nome**: `hash(name) % len(palette)` para selecionar cor da borda entre 8 cores definidas. Estável por sessão (hash é determinístico). Implementado via `set-pane-option` em cada pane: `@agent_color=colour<N>`, `pane-border-format` com `#[fg=colour<N>,bold] #{@agent} #[default]` e `pane-border-style fg=colour240`.
- **Pane ativo realçado**: hook `after-select-pane` via `set-hook -t <session>` que percorre todos os panes com `pane-border-style fg=colour240` e aplica `fg=#{@agent_color}` no pane ativo. Substitui o `pane-active-border-style` nativo (que não escala para cores por agente).
- **Sidebar sem borda**: `pane-border-format` vazio (string `""`) + `pane-border-style fg=default`. Já tem label "sidebar" via variável de ambiente desde v16.
- **Window options globais ao servidor**: `pane-border-status top`, `pane-border-lines heavy`, `window-status-format ""` e `window-status-current-format ""` são aplicados com `-g` (server-global). `-t <session>` afetaria apenas a janela corrente — os demais panes criados pelo harness ficariam sem configuração.
- **`@agent` já está disponível**: todo pane de harness recebe `@agent=<nome>` desde v18 (requisito "Identidade estável do agente via @Agent pane option"). Basta configurar `pane-border-format "#{@agent}"` nos targets corretos.

## Alternativas descartadas

- `#(tmux display -t '#{pane_id} '#{@agent}'')`: desnecessário — `#{@agent}` é uma interpolação nativa do tmux.
- Formatar data no cli.py e expor via env: mais frágil; `#(date ...)` é padrão tmux e funciona em qualquer sessão sem depender do SAC em execução.

## Testes

- Status bar v3: `status-left` sem `#S:#W` nem lista de janelas; `status-right` com `#{@agent}`, `SAC`, `sac status --mini`, `date` formatado.
- Pane-border-format: `#{@agent}` presente nos harnesses, vazio na sidebar, ativo realçado.
- Cor da borda: hash do nome do agente mapeia para cor estável.
