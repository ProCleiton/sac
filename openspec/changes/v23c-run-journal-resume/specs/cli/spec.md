## ADDED Requirements

### Requirement: Flag --run no comando send
O comando send SHALL aceitar a flag `--run <id>` para associar a mensagem a uma run (agrupador nomeado), criando a run implicitamente no primeiro uso.

#### Scenario: send com --run cria run
- **WHEN** `sac send dev-1 "tarefa A" --run sprint-42` é executado
- **THEN** a mensagem é criada com `run: sprint-42` no cabeçalho
- **AND** a run é criada em `.sac/runs/sprint-42/` se ainda não existir

### Requirement: Comando runs
O sistema SHALL expor o comando `sac runs` para listar runs com status agregado.

#### Scenario: runs lista status
- **WHEN** `sac runs` é executado
- **THEN** cada run em `.sac/runs/` é listada com contagens sent/done/pending

### Requirement: Comando resume
O sistema SHALL expor o comando `sac resume <run_id>` para reconciliar uma run interrompida, re-entregando mensagens não concluídas.

#### Scenario: Resume de run
- **WHEN** `sac resume sprint-42` é executado
- **THEN** o sistema lê o journal da run e re-entrega as mensagens sem `task_done` (pending re-entregues, claimed órfãs reenfileiradas)

#### Scenario: Resume com run inexistente
- **WHEN** `sac resume run-inexistente` é executado
- **THEN** o sistema retorna erro: "run não encontrada"
