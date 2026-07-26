## ADDED Requirements

### Requirement: Aprovação como estado de mensagem
O sistema SHALL suportar o tipo `approval_request` no ciclo de vida da mensagem, com campo de estado `pending | approved | rejected`, além dos estados de localização existentes (inbox/claimed/done).

#### Scenario: approval_request como novo tipo
- **WHEN** uma mensagem do tipo `approval_request` é criada
- **THEN** o arquivo .msg contém os campos `type: approval_request` e `state: pending`
- **AND** após `sac approve`/`sac respond` o estado vira `approved`/`rejected` e a mensagem é movida para `done/`
- **AND** mensagens sem `type` (legado) seguem o fluxo atual inalterado

#### Scenario: user como destino virtual
- **GIVEN** o `user` não tem pane tmux próprio
- **WHEN** uma approval_request chega em `inbox/user/`
- **THEN** o daemon a renderiza no pane do líder (o usuário acompanha via `sac attach` no pane do líder)
- **AND** a mensagem permanece na inbox até ser respondida com `sac approve`/`sac respond`

## MODIFIED Requirements

### Requirement: Daemon de entrega direta
Um daemon opcional SHALL monitorar inbox/claimed de todos os agentes e entregar mensagens diretamente no pane do harness, com suporte a fura-fila (replies entregues mesmo durante tarefa claimed) e backoff exponencial de re-cutucadas. O daemon SHALL também renderizar approval_requests destinadas ao `user` no pane do líder.

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
