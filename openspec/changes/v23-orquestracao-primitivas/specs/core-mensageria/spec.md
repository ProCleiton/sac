## ADDED Requirements

### Requirement: Aprovação como estado de mensagem
O sistema SHALL suportar um estado `approval` no ciclo de vida da mensagem, além dos estados existentes pending/claimed/done.

#### Scenario: approval_request como novo tipo
- **WHEN** uma mensagem do tipo `approval_request` é criada
- **THEN** ela segue o fluxo: inbox → claimed (pelo leader) → done (após approve/respond)
- **AND** durante o período claimed, o leader pode executar `sac approve` ou `sac respond`
- **AND** o arquivo .msg contém os campos `type: approval_request` e `state: pending|approved|rejected`

### Requirement: reply_schema no cabeçalho da mensagem
O sistema SHALL suportar o campo opcional `reply_schema` no cabeçalho do arquivo .msg para validação de reply.

#### Scenario: Cabeçalho com reply_schema
- **WHEN** uma mensagem é criada com `--schema`
- **THEN** o arquivo .msg contém a seção `reply_schema: <definição_do_schema>`
- **AND** o header parsing aceita o campo sem quebrar mensagens existentes

### Requirement: Fan-out como fluxo de mensageria
O sistema SHALL suportar mensagens com cabeçalho `fanout_id` para agrupar replies de um fan-out.

#### Scenario: Mensagem com fanout_id
- **WHEN** `sac fanout` dispara mensagens
- **THEN** cada mensagem .msg contém `fanout_id: <id_do_grupo>`
- **AND** ao enviar a reply, o agente inclui `reply_to_fanout: <id>` no cabeçalho
- **AND** o daemon identifica a reply como parte de um fan-out e gerencia a coleta

### Requirement: Validação de reply no daemon
O daemon SHALL validar replies contra o `reply_schema` da mensagem original antes de entregar ao remetente.

#### Scenario: Daemon valida reply com schema
- **GIVEN** mensagem original com `reply_schema`
- **WHEN** o daemon detecta uma reply na inbox do remetente original
- **THEN** o daemon lê o `reply_schema` do arquivo .msg original
- **AND** valida o corpo da reply contra o schema
- **AND** se válida: entrega a reply (fluxo normal)
- **AND** se inválida: rejeita a reply, devolve erro ao remetente da reply, registra `validation_error` no log

## MODIFIED Requirements

### Requirement: Daemon de entrega direta
Um daemon opcional SHALL monitorar inbox/claimed de todos os agentes e entregar mensagens diretamente no pane do harness, com suporte a fura-fila (replies entregues mesmo durante tarefa claimed) e backoff exponencial de re-cutucadas. O daemon SHALL também monitorar approval_requests, validar replies contra schema e gerenciar fan-outs.

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

#### Scenario: Daemon valida reply com schema
- **GIVEN** mensagem original com `reply_schema`
- **WHEN** uma reply chega na inbox do remetente
- **THEN** o daemon lê o schema do arquivo .msg original
- **AND** valida o corpo da reply contra o schema
- **AND** se válida: entrega a reply e registra `deliver` com `validation: ok`
- **AND** se inválida: rejeita a reply, envia erro ao agente remetente e registra `validation_error`

#### Scenario: Daemon gerencia fan-out
- **GIVEN** fan-out disparado com N targets
- **WHEN** as replies chegam
- **THEN** o daemon coleta as replies em um agregado
- **AND** quando todas as replies são recebidas (ou timeout), entrega o agregado ao solicitante
- **AND** registra evento `fanout_complete` com contagem de replies recebidas

### Requirement: Reply-to-sender
Respostas de agentes SHALL ser enviadas de volta ao remetente original da mensagem. Para mensagens com `reply_schema`, o formato da reply SHALL ser validado contra o schema antes da entrega.

#### Scenario: Resposta automática ao sender
- **WHEN** um agente processa uma mensagem e conclui com `SAC_DONE`
- **THEN** antes de `sac done`, o agente envia o resultado ao `from:` original via `sac send <sender> "<resultado>"`
- **AND** se a mensagem original tinha `reply_schema`, a reply é validada antes da entrega

#### Scenario: Resposta com schema inválido — erro devolvido
- **GIVEN** mensagem original com `reply_schema`
- **WHEN** o agente envia reply em formato inválido
- **THEN** o daemon rejeita a reply
- **AND** o agente remetente recebe mensagem de erro: "reply rejeitada — violação do schema: <detalhes>"
- **AND** a reply original NÃO é entregue ao destinatário
