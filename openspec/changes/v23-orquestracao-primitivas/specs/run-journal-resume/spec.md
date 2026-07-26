## ADDED Requirements

### Requirement: Conceito de run
O sistema SHALL suportar o conceito de "run" como um agrupamento de tarefas relacionadas, com estado persisted em `.sac/runs/<run_id>/`.

#### Scenario: Criação de run
- **WHEN** uma tarefa é iniciada via `sac run <loop> "<descricao>"`
- **THEN** uma run é criada em `.sac/runs/` com id único `<YYYYMMDD>-<HHMMSS>-<NNN>`
- **AND** o diretório da run contém `journal.jsonl` (append-only)
- **AND** a entrada inicial do journal registra `event: run_start`, `loop`, `descricao`

#### Scenario: Checkpoint a cada tarefa
- **WHEN** cada tarefa da run é concluída (via `sac done`)
- **THEN** o daemon persiste checkpoint: registra `event: task_done`, `task_id`, `result_summary` no `journal.jsonl`
- **AND** o checkpoint é fsync'd antes de prosseguir

### Requirement: Resume de run
O sistema SHALL permitir retomar uma run interrompida (crash/reboot) sem re-executar tarefas concluídas.

#### Scenario: Resume com tarefas concluídas
- **WHEN** `sac resume <run_id>` é executado
- **THEN** o sistema lê o `journal.jsonl` para identificar a última tarefa concluída
- **AND** avança para a próxima tarefa não concluída
- **AND** nenhuma tarefa já registrada como `task_done` é re-executada

#### Scenario: Resume de run inexistente
- **WHEN** `sac resume <run_id_invalido>` é executado
- **THEN** o sistema retorna erro: "run não encontrada"

#### Scenario: Resume de run já concluída
- **WHEN** `sac resume <run_id>` é executado em uma run com todas as tarefas concluídas
- **THEN** o sistema informa que a run já foi concluída e exibe o resumo final

### Requirement: Journal de run
O journal da run SHALL ser append-only com fsync a cada entrada, permitindo reconstrução do estado após crash.

#### Scenario: Journal tem todas as entradas
- **GIVEN** uma run com N tarefas concluídas e depois interrompida
- **WHEN** o journal é lido
- **THEN** ele contém N+1 entradas (1x `run_start` + Nx `task_done`)
- **AND** a ordem das entradas reflete a ordem de execução

#### Scenario: Journal truncado (crash durante escrita)
- **GIVEN** o journal termina com entrada incompleta (crash durante append)
- **WHEN** o resume tenta ler o journal
- **THEN** a última linha mal-formada é ignorada com warning no log
- **AND** o resume usa a última entrada válida como checkpoint
