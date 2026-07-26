## ADDED Requirements

### Requirement: Comando approve
O sistema SHALL expor o comando `sac approve <id>` para aprovar uma solicitação de aprovação pendente, executável de qualquer pane/diretório com acesso ao SAC_ROOT.

#### Scenario: Approve de approval_request
- **WHEN** `sac approve <id>` é executado para uma approval_request pendente
- **THEN** o estado muda para `approved`
- **AND** o líder recebe reply automática com veredito APROVADO

#### Scenario: Approve de mensagem sem ser approval_request
- **WHEN** `sac approve <id>` é executado para uma mensagem comum
- **THEN** o sistema retorna erro: "mensagem <id> não é uma approval_request"

### Requirement: Comando respond
O sistema SHALL expor o comando `sac respond <id> <veredito> [motivo]` para responder a uma solicitação de aprovação.

#### Scenario: Respond com APPROVED
- **WHEN** `sac respond <id> "APPROVED" "Pode prosseguir"` é executado
- **THEN** o estado muda para `approved` e o líder recebe reply

#### Scenario: Respond com REJECTED
- **WHEN** `sac respond <id> "REJECTED" "Fora do escopo"`
- **THEN** o estado muda para `rejected` e o líder recebe reply com motivo

#### Scenario: Respond com veredito inválido
- **WHEN** `sac respond <id> "INVALIDO"` é executado
- **THEN** o sistema rejeita com erro: "veredito deve ser APPROVED ou REJECTED"

### Requirement: Flag --approval no comando send
O comando send SHALL aceitar a flag `--approval` (apenas para o líder) para criar uma approval_request destinada ao `user`.

#### Scenario: send --approval pelo líder
- **WHEN** o líder executa `sac send user "Podemos fazer deploy?" --approval`
- **THEN** a mensagem é criada como `type: approval_request` na inbox do user

#### Scenario: send --approval por agente não-líder
- **WHEN** um agente aux tenta `sac send user "..." --approval`
- **THEN** o sistema rejeita com erro: "apenas o leader pode enviar approval_request"
