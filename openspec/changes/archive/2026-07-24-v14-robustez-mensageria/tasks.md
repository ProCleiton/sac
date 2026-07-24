## 1. boot_wait por agente — configuração

- [x] 1.1 Escrever teste: `test_config_agent_boot_wait` — `sac.toml` com agente tendo `boot_wait=12`, verificar `cfg.agent("dev-1").boot_wait == 12` e agente sem o campo herda o global (8)
- [x] 1.2 Escrever teste: `test_config_default_boot_wait_8` — config sem `[session] boot_wait` → `cfg.boot_wait == 8`
- [x] 1.3 Implementar: adicionar `boot_wait: float | None = None` ao `AgentConfig`; parser em `load_config` mapeia o campo opcional; `Config.boot_wait` default muda de 3 para 8
- [x] 1.4 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_config.py -q`

## 2. boot_wait por agente — cmd_up

- [x] 2.1 Escrever teste: `test_up_uses_per_agent_boot_wait` — `cmd_up` com FakeRunner e agents com boot_wait diferentes; verificar `time.sleep` chamado com valores diferentes ou não chamado para boot_wait=0
- [x] 2.2 Modificar `cmd_up`: usar `agent.boot_wait if agent.boot_wait is not None else cfg.boot_wait` no sleep antes da injeção do prompt
- [x] 2.3 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_commands.py -q`

## 3. Reply marking — store.send() com reply_to

- [x] 3.1 Escrever teste: `test_store_send_reply_marked` — dev-1 com 1 claimed de leader; send dev-1→leader gera arquivo com cabeçalho `reply_to: <id>`
- [x] 3.2 Escrever teste: `test_store_send_no_claimed_no_reply` — sem claimed, send não adiciona reply_to
- [x] 3.3 Escrever teste: `test_store_send_multi_claimed_no_reply` — 2 claimed de senders diferentes, send não adiciona reply_to (seguro)
- [x] 3.4 Escrever teste: `test_parse_message_with_reply_to` — `Store._parse()` lê arquivo com reply_to e retorna `Message.reply_to` correto
- [x] 3.5 Escrever teste: `test_parse_message_without_reply_to` — arquivo antigo sem reply_to → `reply_to is None` (compatibilidade)
- [x] 3.6 Implementar `Message.reply_to: str | None = None` no dataclass; `_parse()` extrai `reply_to` via `meta.get("reply_to")`; `send()` infere reply_to pela lógica de 1 claimed com sender match e adiciona cabeçalho
- [x] 3.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_store.py -q`

## 4. Daemon — deliver_reply (auto-ack de reply na entrega)

- [x] 4.1 Escrever teste: `test_daemon_deliver_reply` — daemon entrega mensagem com reply_to: verifica que após paste, msg vai para done (finish_reply) e log "deliver_reply"
- [x] 4.2 Escrever teste: `test_daemon_deliver_task_no_reply` — daemon entrega mensagem sem reply_to: permanece em claimed (inalterado)
- [x] 4.3 Implementar `Store.finish_reply(agent, msg_id)` — move claimed→done, log "deliver_reply"; modificar `Daemon._deliver_next()` para chamar finish_reply se msg.reply_to
- [x] 4.4 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py -q`

## 5. cmd_next — auto-ack de reply no legado

- [x] 5.1 Escrever teste: `test_cmd_next_reply_legacy_auto_ack` — sem daemon, msg com reply_to: após next(), msg vai para done (log deliver_reply ou ack)
- [x] 5.2 Escrever teste: `test_cmd_next_task_legacy_claimed` — sem daemon, msg sem reply_to: claimed (inalterado)
- [x] 5.3 Modificar `cmd_next(store, env)`: após obter msg (via next ou ack), se `msg.reply_to` chamar `store.finish_reply(agent, msg.id)` para garantir auto-ack mesmo no legado
- [x] 5.4 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_commands.py -q`

## 6. Reply cut queue — entrega imediata no daemon

- [x] 6.1 Escrever teste: `test_peek_next_returns_reply` — `store.peek_next("dev-1")` com pending reply retorna (id, reply_to) sem consumir
- [x] 6.2 Escrever teste: `test_peek_next_empty_returns_none` — inbox vazia → None
- [x] 6.3 Implementar `Store.peek_next(agent) -> tuple[str, str | None] | None` em store.py
- [x] 6.4 Escrever teste: `test_daemon_delivers_reply_with_claimed` — daemon com claimed + pending reply: reply entregue (paste + finish_reply), claimed original intacto
- [x] 6.5 Escrever teste: `test_daemon_skips_task_with_claimed` — daemon com claimed + pending task (sem reply_to): task não entregue
- [x] 6.6 Modificar `Daemon._process_agent()`: após stale handling, se `peek_next` mostra reply, chamar `_deliver_next(name)`
- [x] 6.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py -q`

## 7. Rota para user

- [x] 7.1 Escrever teste: `test_cmd_send_user_accepts` — `cmd_send(cfg, store, tmux, "user", "msg")` não lança ConfigError, mensagem em inbox/user/
- [x] 7.2 Escrever teste: `test_cmd_send_user_no_poke` — com tmux ativo, send para user não chama send_keys (não há pane)
- [x] 7.3 Modificar `cmd_send`: `if to != "user": cfg.agent(to)` — pula validação para user
- [x] 7.4 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_commands.py -q`

## 8. Backoff exponencial de poke

- [x] 8.1 Escrever teste: `test_daemon_backoff_doubles_interval` — daemon poka mesma msg 2×: 1º poke imediato, 2º só após 2×poke_stale_after
- [x] 8.2 Escrever teste: `test_daemon_backoff_per_message` — mensagens X e Y têm contadores independentes
- [x] 8.3 Escrever teste: `test_daemon_backoff_caps_at_600s` — após pokes suficientes, intervalo estabiliza em 600s
- [x] 8.4 Escrever teste: `test_notify_sweep_backoff` — notify_sweep com estado de backoff respeita intervalo dobrado
- [x] 8.5 Implementar backoff no daemon: `Daemon._poke_state` e `_poke_count`; método `_poke_interval(msg_id)` com `min(poke_stale_after * 2**n, 600)`
- [x] 8.6 Modificar `notify_sweep` para aceitar `poke_state: dict | None = None`; chamar `_should_poke` se dict
- [x] 8.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py tests/test_notify.py -q`

## 9. log -f resiliente no boot

- [x] 9.1 Escrever teste: `test_cmd_log_follow_waits_for_file`
- [x] 9.2 Escrever teste: `test_cmd_log_no_follow_no_file`
- [x] 9.3 Modificar `cmd_log`: se follow=True e path não existe, loop wait
- [x] 9.4 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_commands.py -q`

## 10. Re-check pré-poke

- [x] 10.1 Escrever teste: `test_notify_sweep_recheck_before_poke`
- [x] 10.2 Modificar `notify_sweep`: re-verificar stale antes do poke
- [x] 10.3 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_notify.py -q`

## 11. status --clean com dry-run

- [x] 11.1 Escrever teste: `test_clean_orphans_dry_run_lists_only`
- [x] 11.2 Escrever teste: `test_clean_orphans_yes_removes`
- [x] 11.3 Escrever teste: `test_clean_log_event_dry_run`
- [x] 11.4 Modificar `Store.clean_orphans(valid, dry_run=False)`
- [x] 11.5 Escrever teste: `test_cmd_status_dry_run`
- [x] 11.6 Escrever teste: `test_cmd_status_clean_yes`
- [x] 11.7 Modificar `cmd_status(cfg, store, tmux, clean=False, yes=False)`
- [x] 11.8 Adicionar flag `--yes` ao parser `status` em `sac/cli.py`
- [x] 11.9 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_store.py tests/test_commands.py -q`

## 12. Chore: PNGs

- [x] 12.1 `git rm docs/logo-candidates/*.png docs/sac-mascot.png`
- [x] 12.2 Verificar `git status` — arquivos em "deleted"

## 13. Chore: uv.lock

- [x] 13.1 Verificar conteúdo de `uv.lock`
- [x] 13.2 `git add uv.lock`
- [x] 13.3 Verificar `git status` — uv.lock em "new file"

## 14. Validação final

- [x] 14.1 `rtk test uv run --with-editable . python -m pytest tests/ -q` — 135 passed
- [x] 14.2 `openspec validate v14-robustez-mensageria`
- [x] 14.3 `git status --short` — apenas arquivos intencionais alterados
