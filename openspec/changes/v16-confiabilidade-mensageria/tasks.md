## 1. deliver_reply com verificação + fallback

- [x] 1.1 Escrever teste: `test_deliver_reply_unknown_agent` — mock `cfg.agent()` lança KeyError, daemon registra `loop_error` e não perde mensagem
- [x] 1.2 Escrever teste: `test_deliver_reply_pane_not_found` — mock `find_pane_id` retorna None, daemon loga aviso e mensagem permanece na inbox
- [x] 1.3 Escrever teste: `test_send_fallback_poke_sem_daemon` — `sac send` sem daemon envia poke com Enter + hint para pane do agente
- [x] 1.4 Implementar verificação de destino em `Daemon._process_agent()`: try/except `cfg.agent(to)`, log `loop_error` se falhar
- [x] 1.5 Implementar verificação de pane em `Daemon._deliver_next()`: se `find_pane_id` retorna None, loga aviso e retorna sem perder mensagem
- [x] 1.6 Modificar `cmd_send` sem daemon: usar `tmux.poke_with_enter` com delay + Enter + hint
- [x] 1.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py tests/test_commands.py -q`

## 2. done com atomicidade (write-ahead + fsync + verificação)

- [x] 2.1 Escrever teste: `test_finish_write_ahead_log` — mock `log.jsonl` verifica que evento done é escrito ANTES do move
- [x] 2.2 Escrever teste: `test_finish_move_fails` — mock `shutil.move` lança OSError, finish() NÃO imprime "concluída ✅" e loga `loop_error`
- [x] 2.3 Escrever teste: `test_finish_move_orphan` — mock `shutil.move` não move (src existe após), finish() loga erro e retorna False
- [x] 2.4 Escrever teste: `test_finish_success_verification` — move bem-sucedido, src não existe, imprime "concluída ✅", log tem evento done
- [x] 2.5 Implementar `Store.finish()` com nova ordem: log.write + flush + fsync → shutil.move → verify src gone → print resultado
- [x] 2.6 Implementar `Store._log_done()`: método auxiliar que serializa dict, abre log.jsonl append, escreve, fsync, fecha
- [x] 2.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_store.py -q`

## 3. SAC_ROOT explícito

- [x] 3.1 Escrever teste: `test_store_root_explicit` — `Store(root=Path("/tmp/test"))` resolve inbox para `/tmp/test/.sac/inbox/`
- [x] 3.2 Escrever teste: `test_store_root_none_fallback` — `Store(root=None)` resolve para `Path.cwd() / ".sac"`
- [x] 3.3 Escrever teste: `test_config_session_root` — sac.toml com `[session] root = "/custom/path"`, `Config.session.root == "/custom/path"`
- [x] 3.4 Escrever teste: `test_config_session_root_relative_rejected` — root relativo rejeitado com ConfigError
- [x] 3.5 Escrever teste: `test_store_root_precedence_cli_over_env` — CLI --sac-root > env SAC_ROOT > config > cwd
- [x] 3.6 Adicionar campo `session.root: str | None = None` em `Config.load()`
- [x] 3.7 Adicionar `resolve_root()` em `Store.__init__`: CLI > env > config > cwd
- [x] 3.8 Adicionar flag `--sac-root` no parser CLI, propagar para `Store.__init__`
- [x] 3.9 Validar root absoluto no config load — rejeitar com ConfigError se relativo
- [x] 3.10 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_store.py tests/test_config.py -q`

## 4. Poke com Enter forçado + delay + hint

- [x] 4.1 Escrever teste: `test_daemon_deliver_with_forced_enter` — mock `tmux.send_keys` verifica duas chamadas: body (literal) e Enter (com delay), e hint ao final
- [x] 4.2 Escrever teste: `test_send_poke_with_hint` — `cmd_send` sem daemon verifica que hint textual está presente no corpo injetado
- [x] 4.3 Implementar helper `poke_with_enter` em `tmux.py`: send-keys -l body → sleep 0.2 → send-keys Enter
- [x] 4.4 Modificar `Daemon._deliver_next()`: usar `poke_with_enter`, adicionar hint `"SAC: mensagem — rode \`sac next\`"` ao final do body
- [x] 4.5 Modificar `cmd_send` sem daemon: usar `poke_with_enter` para o poke manual
- [x] 4.6 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py tests/test_commands.py -q`

## 5. Protocolo de escalação (worker → líder → humano)

- [x] 5.1 Escrever teste: `test_inject_prompt_inclui_contrato` — mock `tmux.paste` verifica que `_inject_prompt` injeta contrato de escalação com o nome do líder ANTES do prompt_file
- [x] 5.2 Escrever teste: `test_inject_sem_prompt_file_recebe_contrato` — agente sem prompt_file recebe o contrato mesmo assim
- [x] 5.3 Escrever teste: `test_contrato_leader_vs_worker` — líder recebe versão "único que fala com o humano"; worker recebe "nunca fala com o humano, reporte ao líder"
- [x] 5.4 Implementar constante `ESCALATION_CONTRACT` (workers) e `ESCALATION_CONTRACT_LEADER` em `commands.py`, formatadas com `cfg.leader.name`
- [x] 5.5 Modificar `_inject_prompt()` para injetar o contrato antes do prompt_file (e mesmo sem prompt_file)
- [x] 5.6 Escrever teste: `test_poke_text_instrui_reporte` — poke do daemon contém "reporte AGORA ao líder" + `sac send <líder>` com nome real
- [x] 5.7 Modificar texto do poke em `Daemon._process_agent()` com instrução de reporte ao líder
- [x] 5.8 Escrever teste: `test_daemon_escalate_apos_n_pokes` — claimed stale + 3 pokes → evento `escalate` no log + mensagem ao líder com sender `daemon`
- [x] 5.9 Escrever teste: `test_daemon_escalate_uma_vez` — 4º poke na mesma mensagem NÃO escala de novo
- [x] 5.10 Escrever teste: `test_config_poke_escalate_after` — campo lido do toml, default 3, rejeita valor < 1
- [x] 5.11 Implementar `poke_escalate_after` em `Config` ([session], default 3, validação >= 1)
- [x] 5.12 Implementar escalonamento no daemon: `_escalated` set, `store.send` ao líder, log `escalate`
- [x] 5.13 Atualizar templates `prompts/dev.md`, `prompts/auditor.md` (regra: nunca falar com o humano, reportar ao líder) e `prompts/leader.md` (único canal com o humano)
- [x] 5.14 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py tests/test_commands.py tests/test_config.py -q`

## 6. Validação final

- [x] 6.1 `rtk test uv run --with-editable . python -m pytest tests/ -q` — 195+ passed
- [x] 6.2 `openspec validate v16-confiabilidade-mensageria`
- [x] 6.3 `rtk git status --short` — apenas arquivos intencionais

## 7. Teste real ao vivo

- [x] 7.1 Subir sessão de teste (`sac up` se necessário, com config de 2 agentes: leader + dev-1)
- [x] 7.2 Verificar que o prompt injetado no boot contém o contrato de escalação com o nome do líder
- [x] 7.3 Enviar mensagem leader→dev-1: `sac send dev-1 "tarefa de teste v1.6"`
- [x] 7.4 Verificar que dev-1 recebe a mensagem (prompt cutucado)
- [x] 7.5 Dev-1 executa `sac next`, processa, envia reply ao leader
- [x] 7.6 Verificar que leader recebe a reply (reply não se perde)
- [x] 7.7 Leader executa `sac done <id>` — verificar: claimed limpo, log.jsonl tem evento done, "concluída ✅" impresso
- [x] 7.8 Enviar segunda mensagem leader→dev-1: verificar que a fila NÃO está travada
- [x] 7.9 Simular worker sem progresso (dev-1 não dá done): verificar que após N pokes o leader recebe a mensagem de escalonamento do daemon
- [x] 7.10 Inspecionar `log.jsonl`: todos os eventos (send, next, deliver, done, escalate) presentes e consistentes
- [x] 7.11 Se qualquer passo falhar: abortar, corrigir, re-testar (repetir 7.1–7.10)
- [x] 7.12 Registrar resultado do teste real no relatório de encerramento
