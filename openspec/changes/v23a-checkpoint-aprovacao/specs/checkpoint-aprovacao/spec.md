## ADDED Requirements

### Requirement: Mensagem de approval_request
O sistema SHALL suportar um novo tipo de mensagem `approval_request` que representa uma solicitação de aprovação com máquina de estado `pending → approved | rejected`.

#### Scenario: Envio de approval_request pelo líder
- **WHEN** o líder executa `sac send user "<contexto>" --approval`
- **THEN** a mensagem é criada em `inbox/user/` com `type: approval_request`
- **AND** o estado inicial é `pending`
- **AND** o evento `send` é registrado em `log.jsonl` com `type=approval_request`

#### Scenario: approval_request por agente não-líder
- **WHEN** um agente aux tenta enviar `sac send user "..." --approval`
- **THEN** o sistema rejeita com erro: "apenas o leader pode solicitar aprovação"

#### Scenario: Resposta com approved
- **WHEN** o usuário executa `sac approve <id>` de qualquer pane
- **THEN** o estado da mensagem muda para `approved`
- **AND** o veredito é registrado em `log.jsonl` com evento `approval`
- **AND** o líder recebe uma reply automática com o veredito

#### Scenario: Resposta com rejected
- **WHEN** o usuário executa `sac respond <id> "REJECTED" "<motivo>"`
- **THEN** o estado da mensagem muda para `rejected`
- **AND** o motivo é registrado no log
- **AND** o líder recebe uma reply automática com veredito + motivo

#### Scenario: Aprovação duplicada
- **WHEN** `sac approve <id>` é executado em uma mensagem já aprovada/rejeitada
- **THEN** o sistema retorna erro informando que a mensagem já foi respondida

### Requirement: Renderização da approval_request no pane do líder
O daemon SHALL renderizar approval_requests destinadas ao `user` no pane do líder, pois o `user` é um destino virtual sem pane tmux próprio — o usuário acompanha a sessão "cavalgando" o pane do líder via `sac attach`.

#### Scenario: Daemon renderiza pedido no pane do líder
- **GIVEN** daemon ativo e uma approval_request pendente em `inbox/user/`
- **WHEN** o daemon varre a inbox do user
- **THEN** o pedido é renderizado no pane do líder com o texto, o id da mensagem e a instrução de resposta (`sac approve <id>` / `sac respond <id> REJECTED ["motivo"]`)
- **AND** a mensagem permanece em `inbox/user/` até ser respondida

#### Scenario: Resposta de qualquer pane
- **GIVEN** uma approval_request pendente renderizada no pane do líder
- **WHEN** o usuário executa `sac approve <id>` ou `sac respond <id> ...` de qualquer diretório com acesso ao SAC_ROOT
- **THEN** o estado é gravado no .msg e a mensagem é movida para `done/user/`
- **AND** a reply automática ao líder é entregue pelo daemon (fluxo normal de deliver_reply)

### Requirement: Comandos CLI de aprovação
O sistema SHALL expor `sac approve <id>` e `sac respond <id> <veredito> [motivo]` para responder a solicitações de aprovação.

#### Scenario: approve conclui com sucesso
- **WHEN** `sac approve <id>` é executado com um approval_request válido e pendente
- **THEN** a mensagem é movida para `done/` com estado `approved`
- **AND** uma reply automática é enviada ao líder com `veredito: APROVADO`
- **AND** o evento `approval` é registrado em `log.jsonl`

#### Scenario: respond com motivo
- **WHEN** `sac respond <id> "REJECTED" "Fora do escopo da sprint"`
- **THEN** o estado é `rejected`
- **AND** a reply ao líder contém o motivo

#### Scenario: Veredito inválido
- **WHEN** `sac respond <id> "TALVEZ"` é executado
- **THEN** o sistema rejeita com erro: "veredito deve ser APPROVED ou REJECTED"
