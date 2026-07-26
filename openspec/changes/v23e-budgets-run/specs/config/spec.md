## ADDED Requirements

### Requirement: Configuração de budgets no session
O sistema SHALL aceitar campos `max_tasks_per_run`, `max_messages_per_run` e `max_wall_time_per_run` opcionais na seção `[session]` do `sac.toml`.

#### Scenario: Budgets configurados
- **GIVEN** `[session]` contém `max_tasks_per_run = 50`, `max_messages_per_run = 200`, `max_wall_time_per_run = 3600`
- **WHEN** o arquivo é carregado
- **THEN** `session.max_tasks_per_run` é 50
- **AND** `session.max_messages_per_run` é 200
- **AND** `session.max_wall_time_per_run` é 3600

#### Scenario: Budgets ausentes (ilimitado)
- **GIVEN** `[session]` sem campos de budget
- **WHEN** o arquivo é carregado
- **THEN** todos os budgets são 0 (ilimitado)

#### Scenario: Validação — budgets negativos
- **GIVEN** `[session]` com `max_tasks_per_run = -1`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro: "max_tasks_per_run deve ser >= 0"
