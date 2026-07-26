## 0. Setup de dogfooding (worktree + sandbox)

- [ ] 0.1 Criar worktree git dedicado: `git worktree add ../sac-dev v23-orquestracao-primitivas` (working tree principal estável)
- [ ] 0.2 Verificar que toda execução de dev/test usa `SAC_ROOT`/`SAC_CONFIG` descartáveis (diretório temp), nunca o estado da sessão viva `~/.sac-esteira/`
- [ ] 0.3 Verificar que `tmp_path` do pytest isola cada teste (nunca ~/.sac-esteira)
- [ ] 0.4 Planejar merge com esteira parada (`sac down`) + rollback documentado (`git checkout <commit-anterior>` + `sac up`)

## 1. Approval — tipo de mensagem e máquina de estado

- [ ] 1.1 Escrever teste: `test_msg_header_com_type_approval` — arquivo .msg com `type: approval_request` é parseado corretamente, preservando campos existentes
- [ ] 1.2 Escrever teste: `test_msg_sem_type_continuou_funcionando` — mensagem sem `type` (legado) não quebra parsing
- [ ] 1.3 Escrever teste: `test_approval_state_machine` — approval_request nasce pending, approve → approved, respond "REJECTED" → rejected
- [ ] 1.4 Escrever teste: `test_approval_duplicada_rejeitada` — approve em mensagem já respondida retorna erro
- [ ] 1.5 Implementar campo `type` opcional no cabeçalho .msg e parsing
- [ ] 1.6 Implementar campo `state` no cabeçalho .msg: pending/approved/rejected
- [ ] 1.7 Implementar `Store.is_approval_request()`, `Store.set_approval_state()`
- [ ] 1.8 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_checkpoint.py tests/test_store.py -q`

## 2. Approval — comandos CLI e integração com daemon

- [ ] 2.1 Escrever teste: `test_cmd_approve_sucesso` — `sac approve <id>` muda estado e envia reply ao leader com veredito
- [ ] 2.2 Escrever teste: `test_cmd_approve_nao_approval_request` — approve em mensagem comum retorna erro
- [ ] 2.3 Escrever teste: `test_cmd_respond_approved` — `sac respond <id> "APPROVED"` funciona
- [ ] 2.4 Escrever teste: `test_cmd_respond_rejected_com_motivo` — `sac respond <id> "REJECTED" "motivo"` funciona
- [ ] 2.5 Escrever teste: `test_cmd_respond_veredito_invalido` — rejeita veredito diferente de APPROVED/REJECTED
- [ ] 2.6 Escrever teste: `test_cmd_send_approval_leader` — leader pode usar `sac send --approval`
- [ ] 2.7 Escrever teste: `test_cmd_send_approval_aux_rejeitado` — agente aux não pode usar `--approval`
- [ ] 2.8 Implementar `cmd_approve` em commands.py
- [ ] 2.9 Implementar `cmd_respond` em commands.py
- [ ] 2.10 Implementar flag `--approval` em `cmd_send` com validação de role leader
- [ ] 2.11 Registrar comandos `approve` e `respond` no parser CLI
- [ ] 2.12 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_checkpoint.py tests/test_commands.py -q`

## 3. Run journal — estrutura e checkpoint

- [ ] 3.1 Escrever teste: `test_run_journal_create` — criar run em `.sac/runs/<id>/` com `journal.jsonl` e entrada `run_start`
- [ ] 3.2 Escrever teste: `test_run_journal_append_task_done` — checkpoint task_done com id e resumo
- [ ] 3.3 Escrever teste: `test_run_journal_fsync` — entrada é fsync'd antes do retorno
- [ ] 3.4 Escrever teste: `test_run_journal_truncado` — última linha mal-formada é ignorada no resume
- [ ] 3.5 Escrever teste: `test_run_resume_avanca` — resume após 3 tarefas concluídas avança para a 4ª
- [ ] 3.6 Escrever teste: `test_run_resume_completa` — resume de run já concluída informa que está completa
- [ ] 3.7 Escrever teste: `test_run_resume_inexistente` — run_id inválido retorna erro
- [ ] 3.8 Implementar `RunJournal` em `sac/run.py` (create, log_entry, read_checkpoint, next_pending, is_complete)
- [ ] 3.9 Expandir `cmd_run` para criar diretório `.sac/runs/<id>/` e escrever entrada `run_start`
- [ ] 3.10 Modificar `Store.finish()` para aceitar `run_id` opcional e chamar `RunJournal.log_entry()`
- [ ] 3.11 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_run.py tests/test_store.py -q`

## 4. Run resume — comando CLI e integração

- [ ] 4.1 Escrever teste: `test_cmd_resume_apos_crash` — sac resume retoma da última checkpoint válida
- [ ] 4.2 Escrever teste: `test_cmd_resume_sem_run_id` — erro se run_id não for fornecido
- [ ] 4.3 Escrever teste: `test_cmd_run_com_resume_rejeita_id_duplicado` — run com id já existente é rejeitada
- [ ] 4.4 Implementar `cmd_resume` em commands.py
- [ ] 4.5 Registrar comando `resume` no parser CLI
- [ ] 4.6 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_run.py tests/test_commands.py -q`

## 5. Reply schema — validação

- [ ] 5.1 Escrever teste: `test_validate_reply_schema_ok` — reply válida contra schema passa
- [ ] 5.2 Escrever teste: `test_validate_reply_schema_invalido` — reply inválida retorna erros
- [ ] 5.3 Escrever teste: `test_validate_reply_schema_sem_schema` — sem schema, sem validação (sempre passa)
- [ ] 5.4 Escrever teste: `test_validate_reply_schema_enum` — valida enum corretamente
- [ ] 5.5 Escrever teste: `test_validate_reply_schema_required` — valida campos obrigatórios
- [ ] 5.6 Escrever teste: `test_validate_reply_schema_complexo` — object aninhado com propriedades
- [ ] 5.7 Escrever teste: `test_schema_invalido_rejeitado_no_send` — schema mal-formado rejeita o envio
- [ ] 5.8 Implementar `ReplyValidator` em `sac/reply_validator.py`: validate(reply_body, schema) → (bool, errors[])
- [ ] 5.9 Suportar tipos: object, string, number, array, enum, required
- [ ] 5.10 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_reply_validator.py -q`

## 6. Reply schema — integração no daemon e flag --schema

- [ ] 6.1 Escrever teste: `test_daemon_valida_reply_com_schema` — daemon valida reply contra schema da msg original antes de entregar
- [ ] 6.2 Escrever teste: `test_daemon_rejeita_reply_invalida` — daemon rejeita reply inválida e envia erro ao agente
- [ ] 6.3 Escrever teste: `test_daemon_validation_error_logged` — evento `validation_error` registrado no log
- [ ] 6.4 Escrever teste: `test_cmd_send_com_schema` — `sac send --schema <json>` adiciona reply_schema ao .msg
- [ ] 6.5 Escrever teste: `test_cmd_send_schema_default_config` — schema default do sac.toml aplicado se presente
- [ ] 6.6 Implementar validação de reply no daemon (antes de deliver_reply)
- [ ] 6.7 Implementar flag `--schema` em `cmd_send`
- [ ] 6.8 Implementar campo `reply_schema_default` no config
- [ ] 6.9 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_daemon.py tests/test_commands.py tests/test_reply_validator.py -q`

## 7. Fan-out — comando e disparo

- [ ] 7.1 Escrever teste: `test_fanout_cria_mensagens_para_cada_target` — N targets criam N mensagens com fanout_id comum
- [ ] 7.2 Escrever teste: `test_fanout_template_vazio_rejeitado` — template vazio retorna erro
- [ ] 7.3 Escrever teste: `test_fanout_sem_targets_rejeitado` — sem targets retorna erro
- [ ] 7.4 Escrever teste: `test_fanout_com_timeout_flag` — flag --timeout é aceita e aplicada
- [ ] 7.5 Escrever teste: `test_fanout_evento_logged` — evento fanout registrado com contagem de targets
- [ ] 7.6 Implementar `FanOutManager` em `sac/fanout.py`: dispara mensagens com cabeçalho `fanout_id`
- [ ] 7.7 Implementar `cmd_fanout` em commands.py
- [ ] 7.8 Registrar comando `fanout` no parser CLI
- [ ] 7.9 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_fanout.py tests/test_commands.py -q`

## 8. Fan-out — coleta de replies e agregado

- [ ] 8.1 Escrever teste: `test_fanout_coleta_todas_replies` — N replies → agregado com chaves corretas
- [ ] 8.2 Escrever teste: `test_fanout_coleta_parcial_timeout` — timeout expira → agregado parcial com TIMEOUT nos ausentes
- [ ] 8.3 Escrever teste: `test_fanout_agregado_entregue_ao_solicitante` — agregado enviado como mensagem ao solicitante
- [ ] 8.4 Escrever teste: `test_fanout_reply_com_fanout_id_incluido` — reply do agente contém `reply_to_fanout`
- [ ] 8.5 Escrever teste: `test_fanout_daemon_morto_sem_coleta` — sem daemon, fan-out cria msgs mas não coleta (documentado)
- [ ] 8.6 Implementar `FanOutCollector` em `sac/fanout.py`: coleta replies, monta agregado, gerencia timeout com threading.Timer
- [ ] 8.7 Integrar coleta no daemon: ao processar reply com `reply_to_fanout`, encaminhar ao FanOutCollector
- [ ] 8.8 Persistir agregado parcial em `.sac/fanout/<id>.partial.json` para resiliência a crash
- [ ] 8.9 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_fanout.py tests/test_daemon.py -q`

## 9. Budgets — tracker e enforce

- [ ] 9.1 Escrever teste: `test_budget_task_exceeded` — max_tasks_per_run=3, 4ª tarefa rejeitada
- [ ] 9.2 Escrever teste: `test_budget_message_exceeded` — max_messages_per_run=5, 6ª msg rejeitada
- [ ] 9.3 Escrever teste: `test_budget_wall_time_exceeded` — max_wall_time_per_run=10, após 10s run suspensa
- [ ] 9.4 Escrever teste: `test_budget_unlimited_default` — teto=0 não aplica limite
- [ ] 9.5 Escrever teste: `test_budget_grace_period` — wall time excedido, tarefa claimed tem 30s para concluir
- [ ] 9.6 Escrever teste: `test_budget_resume_reseta_contadores` — resume de run zera contadores (com snapshot no journal)
- [ ] 9.7 Escrever teste: `test_budget_snapshot_no_journal` — checkpoint registra consumo acumulado
- [ ] 9.8 Implementar `BudgetTracker` em `sac/budget.py`: check_task, check_message, check_wall_time, snapshot
- [ ] 9.9 Implementar campos de config `max_tasks_per_run`, `max_messages_per_run`, `max_wall_time_per_run` com validação >= 0
- [ ] 9.10 Implementar enforce no daemon e `sac send`: verificar budgets antes de criar mensagem
- [ ] 9.11 Implementar grace period (threading.Timer, 30s após wall time)
- [ ] 9.12 Implementar snapshot no journal a cada checkpoint (budget_snapshot no RunJournal)
- [ ] 9.13 Registrar justificativa de exclusão de budgets de token/USD no design.md (já incluído)
- [ ] 9.14 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_budget.py tests/test_config.py tests/test_daemon.py -q`

## 10. Validação final

- [ ] 10.1 `rtk test uv run --with-editable . python -m pytest tests/ -q` — 340+ passed
- [ ] 10.2 `openspec validate v23-orquestracao-primitivas`
- [ ] 10.3 `rtk git status --short` — apenas arquivos intencionais
