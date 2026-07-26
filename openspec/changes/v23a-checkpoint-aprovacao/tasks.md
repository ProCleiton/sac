## 1. Approval — tipo de mensagem e máquina de estado

- [ ] 1.1 Escrever teste: `test_msg_header_com_type_approval` — arquivo .msg com `type: approval_request` é parseado corretamente, preservando campos existentes
- [ ] 1.2 Escrever teste: `test_msg_sem_type_continua_funcionando` — mensagem sem `type` (legado) não quebra parsing
- [ ] 1.3 Escrever teste: `test_approval_state_machine` — approval_request nasce pending, approve → approved, respond "REJECTED" → rejected
- [ ] 1.4 Escrever teste: `test_approval_duplicada_rejeitada` — approve em mensagem já respondida retorna erro
- [ ] 1.5 Implementar campo `type` opcional no cabeçalho .msg e parsing
- [ ] 1.6 Implementar campo `state` no cabeçalho .msg: pending/approved/rejected
- [ ] 1.7 Implementar `Store.is_approval_request()`, `Store.set_approval_state()`
- [ ] 1.8 Verificar: `python -m pytest tests/test_checkpoint.py tests/test_store.py -q`

## 2. Approval — comandos CLI e integração com daemon

- [ ] 2.1 Escrever teste: `test_cmd_approve_sucesso` — `sac approve <id>` muda estado e envia reply automática ao líder com veredito
- [ ] 2.2 Escrever teste: `test_cmd_approve_nao_approval_request` — approve em mensagem comum retorna erro
- [ ] 2.3 Escrever teste: `test_cmd_respond_approved` — `sac respond <id> "APPROVED"` funciona
- [ ] 2.4 Escrever teste: `test_cmd_respond_rejected_com_motivo` — `sac respond <id> "REJECTED" "motivo"` funciona
- [ ] 2.5 Escrever teste: `test_cmd_respond_veredito_invalido` — rejeita veredito diferente de APPROVED/REJECTED
- [ ] 2.6 Escrever teste: `test_cmd_send_approval_leader` — leader pode usar `sac send user "..." --approval`
- [ ] 2.7 Escrever teste: `test_cmd_send_approval_aux_rejeitado` — agente aux não pode usar `--approval`
- [ ] 2.8 Escrever teste: `test_daemon_renderiza_approval_no_pane_do_leader` — approval_request em `inbox/user/` é renderizada no pane do líder (user não tem pane), com id e instrução de resposta
- [ ] 2.9 Implementar `cmd_approve` em commands.py
- [ ] 2.10 Implementar `cmd_respond` em commands.py
- [ ] 2.11 Implementar flag `--approval` em `cmd_send` com validação de role leader
- [ ] 2.12 Implementar renderização de approval_request no pane do líder no daemon
- [ ] 2.13 Registrar comandos `approve` e `respond` no parser CLI
- [ ] 2.14 Verificar: `python -m pytest tests/test_checkpoint.py tests/test_commands.py tests/test_daemon.py -q`

## 3. Fechamento

- [ ] 3.1 Suíte completa verde com simulação de CI: `env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" python -m pytest tests/ -q` — 486+ passed
- [ ] 3.2 `openspec validate v23a-checkpoint-aprovacao --strict` — válido
- [ ] 3.3 Validação ao vivo em diretório descartável (`SAC_HOME`/`SAC_ROOT`/socket em `/tmp`): subir sessão, líder envia `sac send user "..." --approval`, usuário responde com `sac approve`/`sac respond` de outro pane, líder recebe reply automática
- [ ] 3.4 `git status --short` — apenas arquivos intencionais
