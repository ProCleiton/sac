# Tasks: v19-boot-size-kill-revive

## Fix 1 — Tamanho explícito da sessão no `sac up`
- [x] 1.1 Teste: config aceita `[session] width`/`height` opcionais; default 220x50; rejeita valor não-inteiro/negativo (tests/test_config.py)
- [x] 1.2 Implementar parsing de `width`/`height` em `Config` (sac/config.py)
- [x] 1.3 Teste: `Tmux.new_session` inclui `-x <w> -y <h>` no comando (tests/test_tmux.py)
- [x] 1.4 Implementar `width`/`height` em `Tmux.new_session` (sac/tmux.py)
- [x] 1.5 Teste: `cmd_up` repassa o tamanho da config na criação da sessão (tests/test_commands.py)
- [x] 1.6 Implementar repasse em `cmd_up` (sac/commands.py)

## Fix 2 — `sac kill` revive pane morto
- [x] 2.1 Teste: `sac kill` com pane inexistente recria o harness na janela correta (legado: janela = nome do agente; grid: janela da gramática `[windows]`) — split a partir da sidebar, `@agent`, título, prompt injetado, alerta de claimed
- [x] 2.2 Teste: `sac kill` retorna erro quando a janela/sidebar do agente também não existe
- [x] 2.3 Implementar caminho de revive em `cmd_kill` (sac/commands.py), resolvendo janela via `layout.build_plan` quando `cfg.windows` existe

## Fix 3 — Env de sessão nos panes (SAC_ROOT + SAC_CONFIG)
- [x] 3.1 Teste: CLI usa `$SAC_CONFIG` como default de `--config` quando definido (tests/test_cli.py)
- [x] 3.2 Implementar default `SAC_CONFIG` em `_build_parser` (sac/cli.py)
- [x] 3.3 Teste: `cmd_up` exporta `SAC_ROOT`+`SAC_CONFIG` nos panes (harness, sidebar, dash); `cmd_kill` idem na recriação (tests/test_commands.py)
- [x] 3.4 Implementar exportação de env nos pontos de criação de pane (sac/commands.py) e repasse de `config_path` em cli.py

## Fix 4 — Agnosticidade do init (sem referências de ambiente)
- [x] 4.1 Teste: templates/notas/fonte do init sem referências de ambiente (`esteira/`, deepseek, `/home/`) (tests/test_init.py)
- [x] 4.2 Tornar `KIMI_NOTE`/`OPENCODE_NOTE`/exemplo do questionário genéricos (sac/init.py)

## Fechamento
- [x] 5.1 Remover `sac.toml` + `.sac/` + `prompts/` de dentro do repo sac (dogfooding equivocado — pedido do usuário)
- [x] 5.2 Suíte 100% verde (`pytest tests/ -q`)
- [x] 5.3 `openspec validate v19-boot-size-kill-revive`
- [x] 5.4 Validação ao vivo: `sac down && sac up` na esteira do workspace — 8 agentes com pane vivo (incluindo docs e deployment), `sac kill` num agente vivo e num com pane morto, e comandos `sac` do agente resolvendo a sessão certa mesmo com cwd fora da raiz
