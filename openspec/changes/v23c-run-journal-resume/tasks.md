## 1. Run — agrupador via run_id e journal

- [ ] 1.1 Escrever teste: `test_send_com_run_cria_run_implicitamente` — primeira mensagem com `--run <id>` cria `.sac/runs/<id>/journal.jsonl` com entrada `run_start`
- [ ] 1.2 Escrever teste: `test_send_com_run_existente_nao_recria` — mensagem seguinte com o mesmo run_id apenas registra `task_sent`, sem duplicar `run_start`
- [ ] 1.3 Escrever teste: `test_msg_header_com_run_id` — .msg contém campo `run: <id>` no cabeçalho; mensagens sem `run` (legado) seguem inalteradas
- [ ] 1.4 Escrever teste: `test_run_journal_append_task_done` — `sac done` de mensagem com run_id registra `task_done` com id e resumo
- [ ] 1.5 Escrever teste: `test_run_journal_fsync` — entrada é fsync'd antes do retorno
- [ ] 1.6 Escrever teste: `test_run_journal_truncado` — última linha mal-formada é ignorada na leitura, última entrada válida prevalece
- [ ] 1.7 Implementar `RunJournal` em `sac/run.py` (ensure, log_entry, read_entries, pending_messages, is_complete)
- [ ] 1.8 Implementar flag `--run` em `cmd_send` + campo `run` no cabeçalho + registro de `task_sent`
- [ ] 1.9 Modificar `Store.finish()` para registrar `task_done` no journal quando a mensagem tem `run`
- [ ] 1.10 Verificar: `python -m pytest tests/test_run.py tests/test_store.py -q`

## 2. Runs — listagem e resume

- [ ] 2.1 Escrever teste: `test_cmd_runs_lista` — `sac runs` lista runs com contagens sent/done/pending e status
- [ ] 2.2 Escrever teste: `test_cmd_runs_sem_runs` — sem `.sac/runs/`, informa que não há runs
- [ ] 2.3 Escrever teste: `test_cmd_resume_reentrega_pending` — mensagens pending da run são re-entregues ao agente
- [ ] 2.4 Escrever teste: `test_cmd_resume_reenfileira_claimed_orfa` — claimed órfã (além de `poke_stale_after` sem done) volta para a inbox e é re-entregue
- [ ] 2.5 Escrever teste: `test_cmd_resume_nao_toca_done` — mensagens com `task_done` no journal nunca são re-executadas
- [ ] 2.6 Escrever teste: `test_cmd_resume_run_completa` — resume de run com tudo done informa conclusão
- [ ] 2.7 Escrever teste: `test_cmd_resume_inexistente` — run_id inválido retorna erro "run não encontrada"
- [ ] 2.8 Implementar `cmd_runs` em commands.py
- [ ] 2.9 Implementar `cmd_resume` em commands.py (reconciliação journal × fila)
- [ ] 2.10 Registrar comandos `runs` e `resume` no parser CLI
- [ ] 2.11 Verificar: `python -m pytest tests/test_run.py tests/test_commands.py -q`

## 3. Fechamento

- [ ] 3.1 Suíte completa verde com simulação de CI: `env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" python -m pytest tests/ -q` — 486+ passed
- [ ] 3.2 `openspec validate v23c-run-journal-resume --strict` — válido
- [ ] 3.3 Validação ao vivo em diretório descartável (`SAC_HOME`/`SAC_ROOT`/socket em `/tmp`): enviar 2 tarefas com `--run`, concluir 1, derrubar daemon, rodar `sac runs` e `sac resume <id>`, conferir re-entrega da pendente e journal intacto
- [ ] 3.4 `git status --short` — apenas arquivos intencionais
