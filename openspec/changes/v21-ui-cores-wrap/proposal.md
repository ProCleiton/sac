## Why

O usuário homologou a v20 ao vivo na esteira real e pediu 3 melhorias de UI:

1. **Status bar com visual CCB** — as cores genéricas `colour213/203/215` sem segmentos destoam do modelo CCB (catppuccin com separadores powerline).
2. **Caixas comms/tips mais largas** — o conteúdo das seções da sidebar trunca rente à borda; falta padding interno.
3. **Quebra de linha na sidebar** — entradas da árvore de agentes e linhas longas das seções comms/tips truncam em vez de quebrar com indentação.

## What Changes

- **Status bar v4 — paleta e segmentos CCB**: reescrever `status-left` e `status-right` no estilo powerline com a paleta do CCB (extraída de `terminal_runtime/tmux_theme.py`: `mode_accent` dinâmico pink/mauve/red, `focus_bg` red, `version_bg` mauve, `indicator_bg` blue, `time_bg` peach, `background` base #1e1e2e). Esquerda: segmento de modo + separador + session_name. Direita: agente da janela ativa | `SAC <versão>` | `sac status --mini` | `dd/MM dow HH:MM`. O CONTEÚDO é o mesmo da v20; muda apenas o estilo visual (cores, segmentos, separadores).
- **Caixas comms/tips mais largas**: aumentar o padding base da função `_section()` (constante `22` → valor entre 23 e 26, a definir no design) para que o conteúdo das seções tenha mais espaço interno sem colar na borda da moldura.
- **Quebra de linha com indentação na sidebar**: substituir o truncamento (`_truncate_ansi`) por wrapping automático no `_render_sidebar`. Para a árvore de agentes, a continuação da linha deve alinhar com o início do nome do agente (após o conector `├─`/`└─`). Para comms/tips, indentar 2 espaços (mesmo padding do conteúdo).

## Impact

- Código: `sac/commands.py` — `_configure_appearance` (status bar format strings), `_section` (padding), `_render_sidebar` / `_truncate_ansi` (wrap em vez de truncate).
- Specs afetadas: `sessao-tmux` (status bar v3→v4), `layout-grid` (sidebar rendering: boxes width e word wrap).
- Compatibilidade: sem quebra. A paleta catppuccin é hardcoded (não depende de tema externo). Wrap só afeta renderização, sem mudança de layout ou dados.
