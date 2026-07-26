## ADDED Requirements

### Requirement: Comando approve
O sistema SHALL expor o comando `sac approve <id>` para aprovar uma solicitação de aprovação pendente.

#### Scenario: Approve de approval_request
- **WHEN** `sac approve <id>` é executado para uma approval_request pendente
- **THEN** o estado muda para `approved`
- **AND** o leader recebe reply automática com veredito APROVADO

#### Scenario: Approve de mensagem sem ser approval_request
- **WHEN** `sac approve <id>` é executado para uma mensagem comum
- **THEN** o sistema retorna erro: "mensagem <id> não é uma approval_request"

### Requirement: Comando respond
O sistema SHALL expor o comando `sac respond <id> <veredito> [motivo]` para responder a uma solicitação de aprovação.

#### Scenario: Respond com APPROVED
- **WHEN** `sac respond <id> "APPROVED" "Pode prosseguir"` é executado
- **THEN** o estado muda para `approved` e o leader recebe reply

#### Scenario: Respond com REJECTED
- **WHEN** `sac respond <id> "REJECTED" "Fora do escopo"`
- **THEN** o estado muda para `rejected` e o leader recebe reply com motivo

#### Scenario: Respond com veredito inválido
- **WHEN** `sac respond <id> "INVALIDO"` é executado
- **THEN** o sistema rejeita com erro: "veredito deve ser APPROVED ou REJECTED"

### Requirement: Comando fanout
O sistema SHALL expor o comando `sac fanout <template> <targets...>` para disparo paralelo de tarefas.

#### Scenario: Fanout básico
- **WHEN** `sac fanout "Revise o PR" dev-1 auditor` é executado
- **THEN** mensagens são criadas nas inbox de dev-1 e auditor
- **AND** cada mensagem contém cabeçalho `fanout_id: <id>`

#### Scenario: Fanout com timeout
- **WHEN** `sac fanout --timeout 300 "tarefa" dev-1 auditor secops` é executado
- **THEN** o timeout de coleta é 300s

### Requirement: Comando resume
O sistema SHALL expor o comando `sac resume <run_id>` para retomar uma run interrompida.

#### Scenario: Resume de run
- **WHEN** `sac resume 20260726-123000-001` é executado
- **THEN** o sistema lê o journal da run e avança para a próxima tarefa não concluída

#### Scenario: Resume com run inexistente
- **WHEN** `sac resume run-inexistente` é executado
- **THEN** o sistema retorna erro: "run não encontrada"

### Requirement: Flag --schema no comando send
O comando send SHALL aceitar a flag `--schema <json>` para declarar o reply_schema esperado.

#### Scenario: send com schema
- **WHEN** `sac send --schema '{"type": "object", "properties": {"veredito": {"enum": ["OK", "FAIL"]}}}' dev-1 "Valide a config"`
- **THEN** a mensagem é criada com `reply_schema` no cabeçalho

### Requirement: Flag --approval no comando send
O comando send SHALL aceitar a flag `--approval` (apenas para o leader) para criar uma approval_request.

#### Scenario: send --approval
- **WHEN** `sac send --approval user "Podemos fazer deploy?"` é executado pelo leader
- **THEN** a mensagem é criada como `type: approval_request` na inbox do user

#### Scenario: send --approval por agente não-leader
- **WHEN** um agente aux tenta `sac send --approval user "..." `
- **THEN** o sistema rejeita com erro: "apenas o leader pode enviar approval_request"

### Requirement: Flag --budget no comando run
O comando run SHALL aceitar flags opcionais `--max-tasks`, `--max-messages` e `--max-wall-time` para sobrescrever os budgets configurados no sac.toml.

#### Scenario: run com budgets inline
- **WHEN** `sac run --max-tasks 10 --max-wall-time 600 review "Revise o código"` é executado
- **THEN** a run usa os budgets fornecidos em vez dos valores do sac.toml
