## 1. Reply schema — validação

- [ ] 1.1 Escrever teste: `test_validate_reply_schema_ok` — reply válida contra schema passa
- [ ] 1.2 Escrever teste: `test_validate_reply_schema_invalido` — reply inválida retorna erros
- [ ] 1.3 Escrever teste: `test_validate_reply_schema_sem_schema` — sem schema, sem validação (sempre passa)
- [ ] 1.4 Escrever teste: `test_validate_reply_schema_enum` — valida enum corretamente
- [ ] 1.5 Escrever teste: `test_validate_reply_schema_required` — valida campos obrigatórios
- [ ] 1.6 Escrever teste: `test_validate_reply_schema_complexo` — object aninhado com propriedades
- [ ] 1.7 Escrever teste: `test_schema_invalido_rejeitado_no_send` — schema mal-formado rejeita o envio
- [ ] 1.8 Implementar `ReplyValidator` em `sac/reply_validator.py`: validate(reply_body, schema) → (bool, errors[])
- [ ] 1.9 Suportar tipos: object, string, number, array, enum, required
- [ ] 1.10 Verificar: `python -m pytest tests/test_reply_validator.py -q`

## 2. Reply schema — integração no daemon e flag --schema

- [ ] 2.1 Escrever teste: `test_daemon_valida_reply_com_schema` — daemon valida reply contra schema da msg original antes de entregar
- [ ] 2.2 Escrever teste: `test_daemon_rejeita_reply_invalida` — daemon rejeita reply inválida e envia erro ao agente
- [ ] 2.3 Escrever teste: `test_daemon_validation_error_logged` — evento `validation_error` registrado no log
- [ ] 2.4 Escrever teste: `test_cmd_send_com_schema` — `sac send --schema <json>` adiciona reply_schema ao .msg
- [ ] 2.5 Escrever teste: `test_cmd_send_schema_default_config` — schema default do sac.toml aplicado se presente
- [ ] 2.6 Implementar validação de reply no daemon (antes de deliver_reply)
- [ ] 2.7 Implementar flag `--schema` em `cmd_send`
- [ ] 2.8 Implementar campo `reply_schema_default` no config
- [ ] 2.9 Verificar: `python -m pytest tests/test_daemon.py tests/test_commands.py tests/test_reply_validator.py -q`

## 3. Fechamento

- [ ] 3.1 Suíte completa verde com simulação de CI: `env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" python -m pytest tests/ -q` — 486+ passed
- [ ] 3.2 `openspec validate v23b-reply-contrato-estruturado --strict` — válido
- [ ] 3.3 Validação ao vivo em diretório descartável (`SAC_HOME`/`SAC_ROOT`/socket em `/tmp`): enviar tarefa com `--schema`, responder com reply válida e com reply inválida, conferir entrega e `validation_error` no log
- [ ] 3.4 `git status --short` — apenas arquivos intencionais
