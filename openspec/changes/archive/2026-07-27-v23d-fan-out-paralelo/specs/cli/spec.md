## ADDED Requirements

### Requirement: Comando fanout
O sistema SHALL expor o comando `sac fanout <template> <targets...>` para disparo paralelo de tarefas.

#### Scenario: Fanout básico
- **WHEN** `sac fanout "Revise o PR" dev-1 auditor` é executado
- **THEN** mensagens são criadas nas inbox de dev-1 e auditor
- **AND** cada mensagem contém cabeçalho `fanout_id: <id>`

#### Scenario: Fanout com timeout
- **WHEN** `sac fanout --timeout 300 "tarefa" dev-1 auditor secops` é executado
- **THEN** o timeout de coleta é 300s
