## ADDED Requirements

### Requirement: reply_schema no cabeçalho da mensagem
O sistema SHALL suportar o campo opcional `reply_schema` no cabeçalho do arquivo .msg para validação de reply.

#### Scenario: Cabeçalho com reply_schema
- **WHEN** uma mensagem é criada com `--schema`
- **THEN** o arquivo .msg contém a seção `reply_schema: <definição_do_schema>`
- **AND** o header parsing aceita o campo sem quebrar mensagens existentes

### Requirement: Validação de reply no daemon
O daemon SHALL validar replies contra o `reply_schema` da mensagem original antes de entregar ao remetente.

#### Scenario: Daemon valida reply com schema
- **GIVEN** mensagem original com `reply_schema`
- **WHEN** o daemon detecta uma reply na inbox do remetente original
- **THEN** o daemon lê o `reply_schema` do arquivo .msg original
- **AND** valida o corpo da reply contra o schema
- **AND** se válida: entrega a reply (fluxo normal)
- **AND** se inválida: rejeita a reply, devolve erro ao remetente da reply, registra `validation_error` no log

## MODIFIED Requirements

### Requirement: Reply-to-sender
Respostas de agentes SHALL ser enviadas de volta ao remetente original da mensagem. Para mensagens com `reply_schema`, o formato da reply SHALL ser validado contra o schema antes da entrega.

#### Scenario: Resposta automática ao sender
- **WHEN** um agente processa uma mensagem e conclui com `SAC_DONE`
- **THEN** antes de `sac done`, o agente envia o resultado ao `from:` original via `sac send <sender> "<resultado>"`
- **AND** se a mensagem original tinha `reply_schema`, a reply é validada pelo daemon antes da entrega

#### Scenario: Resposta com schema inválido — erro devolvido
- **GIVEN** mensagem original com `reply_schema`
- **WHEN** o agente envia reply em formato inválido
- **THEN** o daemon rejeita a reply
- **AND** o agente remetente recebe mensagem de erro: "reply rejeitada — violação do schema: <detalhes>"
- **AND** a reply original NÃO é entregue ao destinatário
