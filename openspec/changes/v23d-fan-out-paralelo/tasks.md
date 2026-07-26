## 1. Fan-out — comando e disparo

- [ ] 1.1 Escrever teste: `test_fanout_cria_mensagens_para_cada_target` — N targets criam N mensagens com fanout_id comum
- [ ] 1.2 Escrever teste: `test_fanout_template_vazio_rejeitado` — template vazio retorna erro
- [ ] 1.3 Escrever teste: `test_fanout_sem_targets_rejeitado` — sem targets retorna erro
- [ ] 1.4 Escrever teste: `test_fanout_com_timeout_flag` — flag --timeout é aceita e aplicada
- [ ] 1.5 Escrever teste: `test_fanout_evento_logged` — evento fanout registrado com contagem de targets
- [ ] 1.6 Implementar `FanOutManager` em `sac/fanout.py`: dispara mensagens com cabeçalho `fanout_id`
- [ ] 1.7 Implementar `cmd_fanout` em commands.py
- [ ] 1.8 Registrar comando `fanout` no parser CLI
- [ ] 1.9 Verificar: `python -m pytest tests/test_fanout.py tests/test_commands.py -q`

## 2. Fan-out — coleta de replies e agregado

- [ ] 2.1 Escrever teste: `test_fanout_coleta_todas_replies` — N replies → agregado com chaves corretas
- [ ] 2.2 Escrever teste: `test_fanout_coleta_parcial_timeout` — timeout expira → agregado parcial com TIMEOUT nos ausentes
- [ ] 2.3 Escrever teste: `test_fanout_agregado_entregue_ao_solicitante` — agregado enviado como mensagem ao solicitante
- [ ] 2.4 Escrever teste: `test_fanout_reply_com_fanout_id_incluido` — reply do agente contém `reply_to_fanout`
- [ ] 2.5 Escrever teste: `test_fanout_daemon_morto_sem_coleta` — sem daemon, fan-out cria msgs mas não coleta (documentado)
- [ ] 2.6 Implementar `FanOutCollector` em `sac/fanout.py`: coleta replies, monta agregado, gerencia timeout com threading.Timer
- [ ] 2.7 Integrar coleta no daemon: ao processar reply com `reply_to_fanout`, encaminhar ao FanOutCollector
- [ ] 2.8 Persistir agregado parcial em `.sac/fanout/<id>.partial.json` para resiliência a crash
- [ ] 2.9 Verificar: `python -m pytest tests/test_fanout.py tests/test_daemon.py -q`

## 3. Fechamento

- [ ] 3.1 Suíte completa verde com simulação de CI: `env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" python -m pytest tests/ -q` — 486+ passed
- [ ] 3.2 `openspec validate v23d-fan-out-paralelo --strict` — válido
- [ ] 3.3 Validação ao vivo em diretório descartável (`SAC_HOME`/`SAC_ROOT`/socket em `/tmp`): disparar `sac fanout` para 2 agentes, responder de ambos, conferir agregado entregue ao solicitante e arquivo `.sac/fanout/<id>.json`
- [ ] 3.4 `git status --short` — apenas arquivos intencionais
