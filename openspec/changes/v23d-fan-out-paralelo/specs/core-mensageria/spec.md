## ADDED Requirements

### Requirement: Fan-out como fluxo de mensageria
O sistema SHALL suportar mensagens com cabeçalho `fanout_id` para agrupar replies de um fan-out.

#### Scenario: Mensagem com fanout_id
- **WHEN** `sac fanout` dispara mensagens
- **THEN** cada mensagem .msg contém `fanout_id: <id_do_grupo>`
- **AND** ao enviar a reply, o agente inclui `reply_to_fanout: <id>` no cabeçalho
- **AND** o daemon identifica a reply como parte de um fan-out e gerencia a coleta

## MODIFIED Requirements

### Requirement: Daemon de entrega direta
Um daemon opcional SHALL monitorar inbox/claimed de todos os agentes e entregar mensagens diretamente no pane do harness, com suporte a fura-fila (replies entregues mesmo durante tarefa claimed) e backoff exponencial de re-cutucadas. O daemon SHALL também renderizar approval_requests destinadas ao `user` no pane do líder e gerenciar a coleta de replies de fan-outs.

#### Scenario: Daemon entrega mensagem nova
- **GIVEN** daemon ativo (PID file em `.sac/daemon.pid`)
- **WHEN** uma mensagem nova aparece em `inbox/<agente>/`
- **THEN** o daemon injeta o corpo da mensagem no pane do agente via `tmux send-keys -t <pane_id> -l -- <body>` + Enter
- **AND** o evento `deliver` é registrado em `log.jsonl`
- **AND** nenhum poke manual é enviado pelo `sac send`

#### Scenario: Daemon entrega reply com fura-fila
- **GIVEN** o agente tem uma tarefa claimed em andamento
- **WHEN** uma mensagem com `reply_to` chega na inbox do agente
- **THEN** o daemon entrega a resposta imediatamente (usa peek + next para não consumir tarefas)
- **AND** a resposta é movida direto para done (deliver_reply) — sem exigir `sac done`

#### Scenario: Daemon re-cutuca stale
- **GIVEN** uma mensagem em `claimed/<agente>/` há mais de `poke_stale_after` segundos
- **WHEN** o daemon varre o agente
- **THEN** injeta `"SAC: tarefa <id> pendente — rode \`sac done <id>\`"` no pane
- **AND** respeita `notify_interval` entre re-cutucadas do mesmo agente (anti-flood)

#### Scenario: Daemon não entrega mensagens para agentes sem pane
- **WHEN** o daemon tenta entregar para um agente cujo pane_id não é encontrado
- **THEN** a mensagem permanece na inbox (não se perde)
- **AND** o daemon continua tentando no próximo ciclo de poll

#### Scenario: Daemon escreve PID file
- **WHEN** o daemon inicia (`Daemon.run()`)
- **THEN** escreve `daemon.pid` em `.sac/` com o PID do processo
- **AND** ao receber SIGTERM/SIGINT, remove o arquivo

#### Scenario: Daemon renderiza approval_request no pane do líder
- **GIVEN** uma approval_request pendente em `inbox/user/`
- **WHEN** o daemon varre a inbox do user
- **THEN** renderiza o pedido no pane do líder (user não tem pane próprio), incluindo o id e a instrução de resposta
- **AND** registra o evento `approval_prompt` em `log.jsonl`

#### Scenario: Daemon gerencia fan-out
- **GIVEN** fan-out disparado com N targets
- **WHEN** as replies com `reply_to_fanout` chegam
- **THEN** o daemon coleta as replies em um agregado (persistindo parcial em `.sac/fanout/<id>.partial.json`)
- **AND** quando todas as replies são recebidas (ou o timeout expira), entrega o agregado ao solicitante
- **AND** registra evento `fanout_complete` com contagem de replies recebidas
