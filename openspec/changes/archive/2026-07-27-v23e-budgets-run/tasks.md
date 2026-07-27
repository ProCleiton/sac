## 1. Budgets — tracker e enforce

- [x] 1.1 Escrever teste: `test_budget_task_exceeded` — max_tasks_per_run=3, 4ª mensagem com o run_id rejeitada
- [x] 1.2 Escrever teste: `test_budget_message_exceeded` — max_messages_per_run=5, 6ª mensagem sob o run_id rejeitada
- [x] 1.3 Escrever teste: `test_budget_wall_time_exceeded` — max_wall_time_per_run=10, após 10s run suspensa
- [x] 1.4 Escrever teste: `test_budget_unlimited_default` — teto=0 não aplica limite
- [x] 1.5 Escrever teste: `test_budget_grace_period` — wall time excedido, tarefa claimed tem 30s para concluir
- [x] 1.6 Escrever teste: `test_budget_contadores_do_journal` — contadores reconstruídos a partir do journal (sobrevivem a crash/restart, sem reset)
- [x] 1.7 Escrever teste: `test_budget_snapshot_no_journal` — `budget_exceeded` registra dimensão e limite no journal
- [x] 1.8 Escrever teste: `test_budget_override_inline_na_criacao` — flags `--max-tasks`/`--max-wall-time` no primeiro `sac send --run` sobrescrevem o sac.toml
- [x] 1.9 Escrever teste: `test_budget_override_inline_ignorado_em_run_existente` — flags em mensagem seguinte da mesma run são ignoradas com aviso
- [x] 1.10 Implementar `BudgetTracker` em `sac/budget.py`: check_task, check_message, check_wall_time, exceeded, reconstrução via journal
- [x] 1.11 Implementar campos de config `max_tasks_per_run`, `max_messages_per_run`, `max_wall_time_per_run` com validação >= 0
- [x] 1.12 Implementar enforce no `sac send`: verificar budgets da run antes de criar mensagem com `--run`
- [x] 1.13 Implementar enforce no daemon: bloquear entrega de mensagens de run suspensa
- [x] 1.14 Implementar grace period (30s após wall time; derivado do relógio contra o `run_start` do journal em vez de `threading.Timer` — determinístico e sobrevive a restart do daemon)
- [x] 1.15 Implementar registro de budgets efetivos na entrada `run_start` do journal
- [x] 1.16 Verificar: `python -m pytest tests/test_budget.py tests/test_config.py tests/test_daemon.py -q`

## 2. Fechamento

- [x] 2.1 Suíte completa verde com simulação de CI: `env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" python -m pytest tests/ -q` — 486+ passed
- [x] 2.2 `openspec validate v23e-budgets-run --strict` — válido
- [x] 2.3 Validação ao vivo em diretório descartável (`SAC_HOME`/`SAC_ROOT`/socket em `/tmp`): configurar `max_tasks_per_run=2`, enviar 3 mensagens com o mesmo `--run`, conferir rejeição da 3ª com `budget_exceeded` no journal
- [x] 2.4 `git status --short` — apenas arquivos intencionais
