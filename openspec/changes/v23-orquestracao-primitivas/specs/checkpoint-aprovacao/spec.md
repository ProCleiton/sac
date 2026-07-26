## ADDED Requirements

### Requirement: Mensagem de approval_request
O sistema SHALL suportar um novo tipo de mensagem `approval_request` que representa uma solicitação de aprovação com máquina de estado `pending → approved | rejected`.

#### Scenario: Envio de approval_request
- **WHEN** o líder executa `sac send --approval user "<contexto>"`
- **THEN** a mensagem é criada em `inbox/user/` com tipo `approval_request`
- **AND** o estado inicial é `pending`
- **AND** o evento `send` é registrado em `log.jsonl` com `type=approval_request`

#### Scenario: Resposta com approved
- **WHEN** o líder executa `sac approve <id>`
- **THEN** o estado da mensagem muda para `approved`
- **AND** o veredito é registrado em `log.jsonl` com evento `approval`
- **AND** o leader recebe uma reply automática com o veredito

#### Scenario: Resposta com rejected
- **WHEN** o líder executa `sac respond <id> "REJECTED" "<motivo>"`
- **THEN** o estado da mensagem muda para `rejected`
- **AND** o motivo é registrado no log
- **AND** o leader recebe uma reply automática com veredito + motivo

#### Scenario: Aprovação duplicada
- **WHEN** `sac approve <id>` é executado em uma mensagem já aprovada/rejeitada
- **THEN** o sistema retorna erro informando que a mensagem já foi respondida

#### Scenario: approval_request para agente não-leader
- **WHEN** um agente aux tenta enviar `sac send --approval`
- **THEN** o sistema rejeita com erro: "apenas o leader pode solicitar aprovação"

### Requirement: Comandos CLI de aprovação
O sistema SHALL expor `sac approve <id>` e `sac respond <id> <veredito> [motivo]` para responder a solicitações de aprovação.

#### Scenario: approve conclui com sucesso
- **WHEN** `sac approve <id>` é executado com um approval_request válido e pendente
- **THEN** a mensagem é movida para `done/` com veredito `approved`
- **AND** uma reply automática é enviada ao leader com `veredito: APROVADO`
- **AND** o evento `approval` é registrado em `log.jsonl`

#### Scenario: respond com motivo
- **WHEN** `sac respond <id> "REJECTED" "Fora do escopo da sprint"`
- **THEN** o estado é `rejected`
- **AND** a reply ao leader contém o motivo

#### Scenario: Veredito inválido
- **WHEN** `sac respond <id> "TALVEZ"` é executado
- **THEN** o sistema rejeita com erro: "veredito deve ser APPROVED ou REJECTED"
