## 1. deliver_reply com verificação + fallback

- [ ] 1.1 Escrever teste: `test_deliver_reply_unknown_agent` — mock `cfg.agent()` lança KeyError, daemon registra `loop_error` e não perde mensagem
- [ ] 1.2 Escrever teste: `test_deliver_reply_pane_not_found` — mock `find_pane_id` retorna None, daemon loga aviso e mensagem permanece na inbox
- [ ] 1.3 Escrever teste: `test_send_fallback_poke_sem_daemon` — `sac send` sem daemon envia poke com Enter + hint para pane do agente
- [ ] 1.4 Implementar verificação de destino em `Daemon._process_agent()`: try/except `cfg.agent(to)`, log `loop_error` se falhar
- [ ] 1.5 Implementar verificação de pane em `Daemon._deliver_next()`: se `find_pane_id` retorna None, loga aviso e retorna sem perder mensagem
- [ ] 1.6 Modificar `cmd_send` sem daemon: usar `tmux.send_keys` com delay + Enter + hint (reutilizar helper do D4)
- [ ] 1.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py tests/test_commands.py -q`

## 2. done com atomicidade (write-ahead + fsync + verificação)

- [ ] 2.1 Escrever teste: `test_finish_write_ahead_log` — mock `log.jsonl` verifica que evento done é escrito ANTES do move
- [ ] 2.2 Escrever teste: `test_finish_move_fails` — mock `shutil.move` lança OSError, finish() NÃO imprime "concluída ✅" e loga `loop_error`
- [ ] 2.3 Escrever teste: `test_finish_move_orphan` — mock `shutil.move` não move (src existe após), finish() loga erro e retorna False
- [ ] 2.4 Escrever teste: `test_finish_success_verification` — move bem-sucedido, src não existe, imprime "concluída ✅", log tem evento done
- [ ] 2.5 Implementar `Store.finish()` com nova ordem: log.write + flush + fsync → shutil.move → verify src gone → print resultado
- [ ] 2.6 Implementar `Store._log_done()`: método auxiliar que serializa dict, abre log.jsonl append, escreve, fsync, fecha
- [ ] 2.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_store.py -q`

## 3. SAC_ROOT explícito

- [ ] 3.1 Escrever teste: `test_store_root_explicit` — `Store(root=Path("/tmp/test"))` resolve inbox para `/tmp/test/.sac/inbox/`
- [ ] 3.2 Escrever teste: `test_store_root_none_fallback` — `Store(root=None)` resolve para `Path.cwd() / ".sac"`
- [ ] 3.3 Escrever teste: `test_config_session_root` — sac.toml com `[session] root = "/custom/path"`, `Config.session.root == "/custom/path"`
- [ ] 3.4 Escrever teste: `test_config_session_root_relative_rejected` — root relativo rejeitado com ConfigError
- [ ] 3.5 Escrever teste: `test_store_root_precedence_cli_over_env` — CLI --sac-root > env SAC_ROOT > config > cwd
- [ ] 3.6 Adicionar campo `session.root: str | None = None` em `Config.load()`
- [ ] 3.7 Adicionar `resolve_root()` em `Store.__init__`: CLI > env > config > cwd
- [ ] 3.8 Adicionar flag `--sac-root` no parser CLI, propagar para `Store.__init__`
- [ ] 3.9 Validar root absoluto no config load — rejeitar com ConfigError se relativo
- [ ] 3.10 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_store.py tests/test_config.py -q`

## 4. Poke com Enter forçado + delay + hint

- [ ] 4.1 Escrever teste: `test_daemon_deliver_with_forced_enter` — mock `tmux.send_keys` verifica duas chamadas: body (literal) e Enter (com delay), e hint ao final
- [ ] 4.2 Escrever teste: `test_send_poke_with_hint` — `cmd_send` sem daemon verifica que hint textual está presente no corpo injetado
- [ ] 4.3 Implementar helper `_poke_with_enter(tmux, pane_id, body)` em `daemon.py` ou `tmux.py`: send-keys -l body → sleep 0.2 → send-keys Enter
- [ ] 4.4 Modificar `Daemon._deliver_next()`: usar helper `_poke_with_enter`, adicionar hint `"SAC: mensagem — rode \`sac next\`"` ao final do body
- [ ] 4.5 Modificar `cmd_send` sem daemon: usar mesmo helper para o poke manual
- [ ] 4.6 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py tests/test_commands.py -q`

## 5. Validação final

- [ ] 5.1 `rtk test uv run --with-editable . python -m pytest tests/ -q` — 180+ passed
- [ ] 5.2 `openspec validate v16-confiabilidade-mensageria`
- [ ] 5.3 `rtk git status --short` — apenas arquivos intencionais

## 6. Teste real ao vivo

- [ ] 6.1 Subir sessão de teste (`sac up` se necessário, com config de 2 agentes: leader + dev-1)
- [ ] 6.2 Enviar mensagem leader→dev-1: `sac send dev-1 "tarefa de teste v1.6"`
- [ ] 6.3 Verificar que dev-1 recebe a mensagem (prompt cutucado)
- [ ] 6.4 Dev-1 executa `sac next`, processa, envia reply ao leader
- [ ] 6.5 Verificar que leader recebe a reply (reply não se perde)
- [ ] 6.6 Leader executa `sac done <id>` — verificar: claimed limpo, log.jsonl tem evento done, "concluída ✅" impresso
- [ ] 6.7 Enviar segunda mensagem leader→dev-1: verificar que a fila NÃO está travada
- [ ] 6.8 Inspecionar `log.jsonl`: todos os eventos (send, next, deliver, done) presentes e consistentes
- [ ] 6.9 Se qualquer passo falhar: abortar, corrigir, re-testar (repetir 6.1–6.8)
- [ ] 6.10 Registrar resultado do teste real no relatório de encerramento
