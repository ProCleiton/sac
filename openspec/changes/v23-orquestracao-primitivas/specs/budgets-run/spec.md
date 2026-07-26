## ADDED Requirements

### Requirement: Tetos configuráveis por run
O sistema SHALL permitir configurar tetos por run no `sac.toml` seção `[session]` para: número máximo de tarefas lançadas, número máximo de mensagens trocadas e tempo máximo de parede (wall time).

#### Scenario: Configuração de budgets
- **GIVEN** `[session]` contém `max_tasks_per_run = 50`, `max_messages_per_run = 200`, `max_wall_time_per_run = 3600`
- **WHEN** o arquivo é carregado
- **THEN** os budgets são aplicados à run
- **AND** tetos não configurados usam default (0 = ilimitado)

### Requirement: Enforce de budgets pelo daemon
O daemon SHALL monitorar os contadores de cada run ativa e pausar/suspender a run ao atingir qualquer teto.

#### Scenario: Teto de tarefas atingido
- **GIVEN** run com `max_tasks_per_run = 3`
- **WHEN** a 4ª tarefa da run é lançada
- **THEN** o daemon REJEITA o lançamento
- **AND** registra evento `budget_exceeded` em `log.jsonl` com `budget: tasks`, `limit: 3`
- **AND** retorna erro ao solicitante: "limite de tarefas da run excedido (3)"

#### Scenario: Teto de mensagens atingido
- **GIVEN** run com `max_messages_per_run = 10`
- **WHEN** a 11ª mensagem relacionada à run é enviada
- **THEN** o daemon rejeita o envio
- **AND** registra `budget_exceeded` com `budget: messages`

#### Scenario: Teto de wall time atingido
- **GIVEN** run com `max_wall_time_per_run = 60`
- **WHEN** 60 segundos se passam desde o `run_start`
- **THEN** o daemon suspende a run
- **AND** registra `budget_exceeded` com `budget: wall_time`
- **AND** tarefas claimed em andamento podem concluir (grace period de 30s)
- **AND** novas tarefas são rejeitadas

### Requirement: Budget ilimitado (default)
O sistema SHALL tratar teto = 0 como "ilimitado" (sem enforce).

#### Scenario: Budget default (sem config)
- **GIVEN** `sac.toml` sem campos de budget
- **WHEN** a run é iniciada
- **THEN** nenhum teto é aplicado (comportamento livre)
- **AND** o journal registra `budgets: unlimited`

### Requirement: Justificativa para exclusão de budgets de token/USD
O design SHALL documentar explicitamente que budgets de token/USD estão fora de escopo porque o custo por token não é observável de forma harness-agnóstica: o SAC não sabe qual modelo cada harness está usando, nem quantos tokens cada chamada consome. Pi-extensible-workflows só consegue budgets de token porque é single-harness (OpenAI SDK fixo), condição que o SAC (multi-harness) não atende.

#### Scenario: Documentação da decisão
- **GIVEN** o design.md da change
- **WHEN** a seção de budgets é lida
- **THEN** ela contém a justificativa da exclusão de budgets de token/USD
- **AND** menciona que budgets de tarefas/mensagens/tempo são substitutes harness-agnósticos
