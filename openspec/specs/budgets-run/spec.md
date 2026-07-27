# budgets-run Specification

## Purpose
TBD - created by archiving change v23e-budgets-run. Update Purpose after archive.
## Requirements
### Requirement: Tetos configuráveis por run
O sistema SHALL permitir configurar tetos por run no `sac.toml` seção `[session]` para: número máximo de tarefas (mensagens com o run_id), número máximo de mensagens totais trocadas sob o run_id e tempo máximo de parede (wall time) desde o `run_start`.

#### Scenario: Configuração de budgets
- **GIVEN** `[session]` contém `max_tasks_per_run = 50`, `max_messages_per_run = 200`, `max_wall_time_per_run = 3600`
- **WHEN** o arquivo é carregado
- **THEN** os budgets são aplicados a toda run criada
- **AND** tetos não configurados usam default (0 = ilimitado)

#### Scenario: Override inline na criação da run
- **WHEN** `sac send dev-1 "tarefa" --run r1 --max-tasks 10 --max-wall-time 600` é executado e a run `r1` não existe
- **THEN** a run é criada com os budgets fornecidos (persistidos na entrada `run_start` do journal), em vez dos valores do sac.toml

#### Scenario: Override inline ignorado em run existente
- **WHEN** `sac send dev-1 "tarefa" --run r1 --max-tasks 5` é executado e a run `r1` já existe
- **THEN** os budgets da run não são alterados
- **AND** um aviso é emitido informando que as flags só valem na criação da run

### Requirement: Enforce de budgets no send e no daemon
O sistema SHALL verificar os budgets da run antes de criar a mensagem no `sac send` e antes de entregar no daemon, suspendendo a run ao atingir qualquer teto.

#### Scenario: Teto de tarefas atingido
- **GIVEN** run com `max_tasks_per_run = 3` e 3 mensagens já criadas com o run_id
- **WHEN** a 4ª mensagem com o run_id é enviada
- **THEN** o `sac send` REJEITA a criação
- **AND** registra evento `budget_exceeded` em `log.jsonl` e no journal com `budget: tasks`, `limit: 3`
- **AND** retorna erro ao solicitante: "limite de tarefas da run excedido (3)"

#### Scenario: Teto de mensagens atingido
- **GIVEN** run com `max_messages_per_run = 10`
- **WHEN** a 11ª mensagem relacionada à run (tarefa ou reply) é enviada
- **THEN** o envio é rejeitado
- **AND** registra `budget_exceeded` com `budget: messages`

#### Scenario: Teto de wall time atingido
- **GIVEN** run com `max_wall_time_per_run = 60`
- **WHEN** 60 segundos se passam desde o `run_start` do journal
- **THEN** o daemon suspende a run
- **AND** registra `budget_exceeded` com `budget: wall_time`
- **AND** tarefas claimed em andamento podem concluir (grace period de 30s)
- **AND** novas mensagens com o run_id são rejeitadas

#### Scenario: Daemon bloqueia entrega de run suspensa
- **GIVEN** uma run suspensa por budget
- **WHEN** uma mensagem com o run_id chega à inbox (criada antes da suspensão ou por remetente que pulou o gate do send)
- **THEN** o daemon não a entrega
- **AND** registra o bloqueio em `log.jsonl`

### Requirement: Contadores derivados do journal
Os contadores de budget de uma run SHALL ser derivados do journal da run (entradas `task_sent`/`task_done` e timestamps), sobrevivendo a crash/restart sem reset.

#### Scenario: Reconstrução após crash
- **GIVEN** uma run com 3 `task_sent` no journal e o daemon reinicia
- **WHEN** o budget é verificado
- **THEN** o contador de tarefas é 3 (reconstruído do journal), não 0

### Requirement: Budget ilimitado (default)
O sistema SHALL tratar teto = 0 como "ilimitado" (sem enforce).

#### Scenario: Budget default (sem config)
- **GIVEN** `sac.toml` sem campos de budget
- **WHEN** uma run é criada
- **THEN** nenhum teto é aplicado (comportamento livre)
- **AND** o journal registra `budgets: unlimited` na entrada `run_start`

### Requirement: Justificativa para exclusão de budgets de token/USD
O design SHALL documentar explicitamente que budgets de token/USD estão fora de escopo porque o custo por token não é observável de forma harness-agnóstica: o SAC não sabe qual modelo cada harness está usando, nem quantos tokens cada chamada consome. Pi-extensible-workflows só consegue budgets de token porque é single-harness (OpenAI SDK fixo), condição que o SAC (multi-harness) não atende.

#### Scenario: Documentação da decisão
- **GIVEN** o design.md da change
- **WHEN** a seção de budgets é lida
- **THEN** ela contém a justificativa da exclusão de budgets de token/USD
- **AND** menciona que budgets de tarefas/mensagens/tempo são substitutos harness-agnósticos

