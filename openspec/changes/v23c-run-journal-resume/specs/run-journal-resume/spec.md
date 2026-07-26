## ADDED Requirements

### Requirement: Run como agrupador nomeado de mensagens
O sistema SHALL suportar o conceito de "run" como um agrupamento nomeado de mensagens, identificado por um run_id, com estado persistido em `.sac/runs/<run_id>/`. A run é criada implicitamente pela primeira mensagem que carrega o run_id — NÃO existe comando `sac run`.

#### Scenario: Criação implícita de run no send
- **WHEN** `sac send dev-1 "tarefa A" --run sprint-42` é executado e a run `sprint-42` não existe
- **THEN** o diretório `.sac/runs/sprint-42/` é criado com `journal.jsonl`
- **AND** a entrada inicial registra `event: run_start` com o run_id
- **AND** a mensagem criada contém `run: sprint-42` no cabeçalho
- **AND** o journal registra `event: task_sent` com o id da mensagem

#### Scenario: Mensagens seguintes na mesma run
- **WHEN** `sac send auditor "tarefa B" --run sprint-42` é executado e a run já existe
- **THEN** o `run_start` NÃO é duplicado
- **AND** o journal registra `task_sent` para a nova mensagem

#### Scenario: Send sem --run
- **WHEN** `sac send dev-1 "tarefa"` é executado sem `--run`
- **THEN** a mensagem não contém `run` no cabeçalho e nenhum journal é tocado (comportamento atual)

### Requirement: Checkpoint de conclusão no journal
O sistema SHALL registrar `task_done` no journal da run a cada mensagem da run concluída via `sac done`.

#### Scenario: Checkpoint a cada tarefa concluída
- **WHEN** uma mensagem com `run: <id>` é concluída via `sac done <msg_id> "<resumo>"`
- **THEN** o journal da run registra `event: task_done` com `msg_id` e `result_summary`
- **AND** o checkpoint é fsync'd antes do retorno do comando

### Requirement: Listagem de runs
O sistema SHALL expor o comando `sac runs` que lista as runs conhecidas com status agregado.

#### Scenario: Listagem com runs
- **WHEN** `sac runs` é executado com runs em `.sac/runs/`
- **THEN** cada run é listada com contagens de mensagens enviadas/concluídas/pendentes derivadas do journal

#### Scenario: Listagem sem runs
- **WHEN** `sac runs` é executado sem diretório `.sac/runs/`
- **THEN** o sistema informa que não há runs

### Requirement: Resume de run
O sistema SHALL permitir reconciliar uma run interrompida (crash/reboot) re-entregando as mensagens não concluídas, sem re-executar mensagens concluídas.

#### Scenario: Resume re-entrega mensagens pendentes
- **GIVEN** uma run com mensagens `task_sent` sem `task_done` que estão na inbox (pending)
- **WHEN** `sac resume <run_id>` é executado
- **THEN** as mensagens pendentes são re-entregues ao agente (poke/daemon)
- **AND** o evento `resume` é registrado em `log.jsonl`

#### Scenario: Resume reenfileira claimed órfã
- **GIVEN** uma mensagem da run em `claimed/<agente>/` há mais de `poke_stale_after` segundos sem `task_done` (agente/daemon morto)
- **WHEN** `sac resume <run_id>` é executado
- **THEN** a mensagem é movida de volta para `inbox/<agente>/` e re-entregue
- **AND** o requeue é registrado em `log.jsonl`

#### Scenario: Resume nunca re-executa done
- **GIVEN** uma run com 3 mensagens concluídas (`task_done` no journal)
- **WHEN** `sac resume <run_id>` é executado
- **THEN** nenhuma das 3 mensagens é re-executada ou re-entregue

#### Scenario: Resume de run inexistente
- **WHEN** `sac resume <run_id_invalido>` é executado
- **THEN** o sistema retorna erro: "run não encontrada"

#### Scenario: Resume de run já concluída
- **WHEN** `sac resume <run_id>` é executado em uma run com todas as mensagens concluídas
- **THEN** o sistema informa que a run já foi concluída e exibe o resumo

### Requirement: Journal de run
O journal da run SHALL ser append-only com fsync a cada entrada, permitindo reconstrução do estado após crash.

#### Scenario: Journal tem todas as entradas
- **GIVEN** uma run com N mensagens enviadas, M concluídas, e depois interrompida
- **WHEN** o journal é lido
- **THEN** ele contém 1 + N + M entradas (1x `run_start` + Nx `task_sent` + Mx `task_done`)
- **AND** a ordem das entradas reflete a ordem dos eventos

#### Scenario: Journal truncado (crash durante escrita)
- **GIVEN** o journal termina com entrada incompleta (crash durante append)
- **WHEN** o journal é lido (runs/resume)
- **THEN** a última linha mal-formada é ignorada com warning no log
- **AND** a última entrada válida é usada como checkpoint
