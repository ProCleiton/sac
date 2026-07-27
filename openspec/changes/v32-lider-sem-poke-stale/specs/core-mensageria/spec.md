## MODIFIED Requirements

### Requirement: Daemon de entrega direta
Um daemon opcional SHALL monitorar inbox/claimed de todos os agentes e entregar mensagens diretamente no pane do harness, com suporte a fura-fila (replies entregues mesmo durante tarefa claimed) e backoff exponencial de re-cutucadas. O daemon SHALL também renderizar approval_requests destinadas ao `user` no pane do líder e gerenciar a coleta de replies de fan-outs. A re-cutucada de stale SHALL NOT atingir o líder: o pane do líder é o canal direto com o humano, e acima dele não há agente para escalar. Entregas ao líder (replies, escalações de workers, approval_prompts) continuam normalmente.

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
- **GIVEN** uma mensagem em `claimed/<agente>/` há mais de `poke_stale_after` segundos e o agente NÃO é o líder
- **WHEN** o daemon varre o agente
- **THEN** injeta `"SAC: tarefa <id> pendente — rode \`sac done <id>\`"` no pane
- **AND** respeita `notify_interval` entre re-cutucadas do mesmo agente (anti-flood)

#### Scenario: Daemon não re-cutuca o líder
- **GIVEN** uma mensagem em `claimed/<líder>/` há mais de `poke_stale_after` segundos
- **WHEN** o daemon varre o líder
- **THEN** nenhum poke de stale é injetado no pane do líder
- **AND** nenhum evento `poke` é registrado para o líder
- **AND** entregas de novas mensagens ao líder continuam ocorrendo normalmente

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

### Requirement: Stale detection (re-poke) com backoff
Mensagens esquecidas (claimed sem `sac done` há mais de `poke_stale_after` segundos) SHALL ser detectadas para re-cutucada do agente, com backoff exponencial por mensagem (base `poke_stale_after`, teto 5 min). O líder SHALL NOT ser re-cutucado nem monitorado para stale — nem pelo daemon, nem pelo `sac notify` legado: o humano interage diretamente no pane do líder e não há agente acima dele para escalar.

#### Scenario: Identificação de mensagens stale (daemon)
- **GIVEN** daemon ativo
- **WHEN** mensagem em claimed há mais de `poke_stale_after` segundos
- **THEN** o daemon re-cutuca o agente com lembrete específico da tarefa
- **AND** o evento `poke` é registrado em `log.jsonl`

#### Scenario: Identificação de mensagens stale (notify legado)
- **WHEN** `sac notify` varre inbox/claimed de todos agentes (daemon offline)
- **THEN** mensagens com idade > `poke_stale_after` segundos são identificadas
- **AND** o agente é re-cutucado com notificação genérica
- **AND** o evento `poke` é registrado em `log.jsonl`

#### Scenario: Líder excluído da re-cutucada
- **GIVEN** o líder com mensagem claimed há mais de `poke_stale_after` segundos
- **WHEN** o daemon ou o `sac notify` varre os agentes
- **THEN** o líder é ignorado (nenhum poke, nenhum evento no log)
- **AND** os demais agentes seguem sendo re-cutucados normalmente

#### Scenario: Backoff entre pokes da mesma mensagem
- **GIVEN** a mensagem X foi pokada há N segundos
- **WHEN** `notify_sweep` tenta pokear X novamente
- **THEN** o intervalo entre pokes dobra a cada envio (base 120s, teto 600s)
- **AND** o estado de backoff é mantido em memória (dict compartilhado entre daemon e legado)
