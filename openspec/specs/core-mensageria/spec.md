# Core Mensageria

## Purpose
Sistema de mensageria baseado em filesystem para coordenação multi-agente. A "central" é o diretório `.sac/` com subdiretórios `inbox/<agente>/`, `claimed/<agente>/`, `done/<agente>/` e o arquivo `log.jsonl`. Agentes comunicam-se escrevendo/consumindo arquivos `.msg`.

Um daemon opcional (classe `Daemon`) monitora inbox/claimed de cada agente a cada 1s e injeta o corpo da mensagem diretamente no pane do harness via `tmux send-keys -l` — sem necessidade de `sac next` manual.

## Requirements
### Requirement: Armazenamento persistente de mensagens
O sistema SHALL armazenar mensagens como arquivos individuais no filesystem, sem dependência de banco ou processo em execução.

#### Scenario: Envio de mensagem
- **WHEN** uma mensagem é enviada via `sac send <agente> "<corpo>"`
- **THEN** um arquivo `<YYYYMMDD>-<HHMMSS>-<NNN>-from-<sender>.msg` é criado em `inbox/<agente>/` com cabeçalho (id, from, to, ts) e corpo
- **AND** o evento `send` é registrado em `log.jsonl` com timestamp, sender, destinatário e id
- **AND** se o daemon está ativo (daemon.pid existe), NENHUM poke manual é enviado ao pane
- **AND** se o daemon não está ativo, o texto `"SAC: mensagem nova na inbox — rode \`sac next\`"` é injetado via send-keys

#### Scenario: Consumo de mensagem (FIFO)
- **WHEN** um agente executa `sac next`
- **THEN** a mensagem mais antiga (ordem alfabética do nome do arquivo) é movida de `inbox/<agente>/` para `claimed/<agente>/`
- **AND** seu id e conteúdo são impressos na saída padrão
- **AND** o evento `next` é registrado em `log.jsonl`

#### Scenario: Conclusão de mensagem
- **WHEN** um agente executa `sac done <id> "<resumo>"`
- **THEN** a mensagem é movida de `claimed/<agente>/` para `done/<agente>/`
- **AND** o evento `done` é registrado em `log.jsonl` com id e resumo

#### Scenario: Mensagem sem claim
- **WHEN** `sac done <id>` é executado para uma mensagem que não está em `claimed/` do agente
- **THEN** o sistema retorna erro informando que a mensagem não está em posse do agente

#### Scenario: next sem mensagens
- **WHEN** `sac next` é executado e `inbox/<agente>/` está vazio
- **THEN** o sistema retorna indicando que não há mensagens (não bloqueia)

### Requirement: IDs sequenciais com timestamp
O identificador de mensagem SHALL conter timestamp e sequencial para ordenação FIFO natural e rastreabilidade.

#### Scenario: Formato do ID
- **GIVEN** uma mensagem enviada em 24/07/2026 às 10:00:00 como 1ª do segundo
- **THEN** o ID gerado é `20260724-100000-001-from-<sender>`
- **AND** IDs no mesmo segundo recebem sequenciais incrementais (002, 003...)

### Requirement: Log auditável append-only
O sistema SHALL manter um log JSONL de todos os eventos de mensageria para auditoria e depuração.

#### Scenario: Eventos registrados
- **WHEN** mensagens são enviadas, consumidas, concluídas, agentes são cutucados ou o daemon entrega/re-cutuca
- **THEN** cada evento é registrado como uma linha JSON em `.sac/log.jsonl` com timestamp e campos específicos do evento
- **AND** eventos `send` incluem sender e destinatário
- **AND** eventos `next` e `done` incluem agent e id
- **AND** eventos `poke` incluem agent e contagem de mensagens
- **AND** eventos `deliver` (daemon) incluem agent, id e sender

### Requirement: Sentinela de conclusão SAC_DONE
As respostas dos agentes SHALL ser delimitadas por uma sentinela explícita para detecção precisa de fim de processamento.

#### Scenario: Resposta concluída
- **WHEN** um agente termina seu processamento
- **THEN** sua última linha de saída contém apenas `SAC_DONE`
- **AND** `sac recv <agente>` extrai o texto anterior à sentinela como resposta completa
- **AND** `sac recv` retorna exit 0 indicando conclusão

#### Scenario: Resposta em andamento
- **WHEN** `sac recv <agente>` é executado e a sentinela `SAC_DONE` não está presente
- **THEN** o sistema retorna os últimos 500 caracteres e exit 1, indicando processamento em andamento

### Requirement: Daemon de entrega direta
Um daemon opcional SHALL monitorar inbox/claimed de todos os agentes e entregar mensagens diretamente no pane do harness.

#### Scenario: Daemon entrega mensagem nova
- **GIVEN** daemon ativo (PID file em `.sac/daemon.pid`)
- **WHEN** uma mensagem nova aparece em `inbox/<agente>/`
- **THEN** o daemon injeta o corpo da mensagem no pane do agente via `tmux send-keys -t <pane_id> -l -- <body>` + Enter
- **AND** o evento `deliver` é registrado em `log.jsonl`
- **AND** nenhum poke manual é enviado pelo `sac send`

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

### Requirement: Stale detection (re-poke)
Mensagens esquecidas (claimed sem `sac done` há mais de `poke_stale_after` segundos) SHALL ser detectadas para re-cutucada do agente.

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

### Requirement: Reply-to-sender
Respostas de agentes SHALL ser enviadas de volta ao remetente original da mensagem.

#### Scenario: Resposta automática ao sender
- **WHEN** um agente processa uma mensagem e conclui com `SAC_DONE`
- **THEN** antes de `sac done`, o agente envia o resultado ao `from:` original via `sac send <sender> "<resultado>"`
