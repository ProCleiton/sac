## 1. Fan-out — comando e disparo

- [x] 1.1 Escrever teste: `test_fanout_cria_mensagens_para_cada_target` — N targets criam N mensagens com fanout_id comum
- [x] 1.2 Escrever teste: `test_fanout_template_vazio_rejeitado` — template vazio retorna erro
- [x] 1.3 Escrever teste: `test_fanout_sem_targets_rejeitado` — sem targets retorna erro
- [x] 1.4 Escrever teste: `test_fanout_com_timeout_flag` — flag --timeout é aceita e aplicada
- [x] 1.5 Escrever teste: `test_fanout_evento_logged` — evento fanout registrado com contagem de targets
- [x] 1.6 Implementar `FanOutManager` em `sac/fanout.py`: dispara mensagens com cabeçalho `fanout_id`
- [x] 1.7 Implementar `cmd_fanout` em commands.py
- [x] 1.8 Registrar comando `fanout` no parser CLI
- [x] 1.9 Verificar: `python -m pytest tests/test_fanout.py tests/test_commands.py -q`

## 2. Fan-out — coleta de replies e agregado

- [x] 2.1 Escrever teste: `test_fanout_coleta_todas_replies` — N replies → agregado com chaves corretas
- [x] 2.2 Escrever teste: `test_fanout_coleta_parcial_timeout` — timeout expira → agregado parcial com TIMEOUT nos ausentes
- [x] 2.3 Escrever teste: `test_fanout_agregado_entregue_ao_solicitante` — agregado enviado como mensagem ao solicitante
- [x] 2.4 Escrever teste: `test_fanout_reply_com_fanout_id_incluido` — reply do agente contém `reply_to_fanout`
- [x] 2.5 Escrever teste: `test_fanout_daemon_morto_sem_coleta` — sem daemon, fan-out cria msgs mas não coleta (documentado)
- [x] 2.6 Implementar `FanOutCollector` em `sac/fanout.py`: coleta replies, monta agregado, gerencia timeout com threading.Timer
- [x] 2.7 Integrar coleta no daemon: ao processar reply com `reply_to_fanout`, encaminhar ao FanOutCollector
- [x] 2.8 Persistir agregado parcial em `.sac/fanout/<id>.partial.json` para resiliência a crash
- [x] 2.9 Verificar: `python -m pytest tests/test_fanout.py tests/test_daemon.py -q`

## 3. Fechamento

- [x] 3.1 Suíte completa verde com simulação de CI: `env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" python -m pytest tests/ -q` — 486+ passed
- [x] 3.2 `openspec validate v23d-fan-out-paralelo --strict` — válido
- [x] 3.3 Validação ao vivo em diretório descartável (`SAC_HOME`/`SAC_ROOT`/socket em `/tmp`): disparar `sac fanout` para 2 agentes, responder de ambos, conferir agregado entregue ao solicitante e arquivo `.sac/fanout/<id>.json`
- [x] 3.4 `git status --short` — apenas arquivos intencionais
