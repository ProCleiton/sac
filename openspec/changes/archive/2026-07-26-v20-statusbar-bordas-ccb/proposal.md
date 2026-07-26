## Why

A v18 aproximou a status bar e sidebar do modelo CCB, mas dois problemas persistem:

1. **Window-status no lado esquerdo da status bar**: a lista de janelas tmux (ex.: `2:trabalho# 3:apoio# 4:ops# 5:dash#-`) ocupa o `status-left` — "atalhos desnecessários" segundo o designer. O modelo CCB mostra apenas indicador de modo (INPUT/KEY/COPY) + nome do workspace (ex.: "Github").
2. **Moldura de panes sem identidade de agente**: hoje só o pane do lead exibe o nome na borda superior; os demais harnesses mostram o `pane_title`, que o próprio harness sobrescreve (kimi → "Kimi Code" segundos após o boot). A v18 já grava `@agent=<nome>` em todo pane de harness, mas o `pane-border-format` não lê essa option.

## What Changes

- **Status bar v3 — esquerda limpa, direita informativa**:
  - `status-left`: substitui `#S:#W` com lista de janelas por `#{tmux_mode_Indicator} #{session_name}` — modo (INPUT/KEY/COPY) + nome da sessão (ex.: "Github"). Sem lista de janelas.
  - `status-right`: novo formato — `#{@agent} SAC 0.x.y ● #{#(sac status --mini)} #{#(date +"%d/%m %a %H:%M")}` — ou seja: agente da janela ativa, "SAC <versão>", saída de `sac status --mini` e data no formato `dd/MM dow HH:MM`.
  - Mantém: visual limpo sem dicas estáticas (v18), cores existentes.
- **Pane-border-format com `@agent` em todos os panes de harness**:
  - `pane-border-format` lê `#{@agent}` (já gravado em todo pane desde v18), exibindo o nome do agente na moldura superior.
  - Cor da borda derivada do hash do nome do agente (estável por sessão).
  - Pane ativo realçado (v17); sidebar mantém `pane-border-format` vazio e label "sidebar".

## Impact

- Código: `sac/commands.py` (`cmd_up` — status bar format strings + pane-border-format), `sac/tmux.py` (helper de cor por hash).
- Spec: delta em `sessao-tmux` (status bar v3 + identidade via @Agent na moldura).
- Compatibilidade: `pane-border-format` e `@agent` são features do tmux 3.2+ (já requerido). Nenhuma mudança de config exigida.
