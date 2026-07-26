## ADDED Requirements

### Requirement: reply_schema declarado por tarefa
O sistema SHALL permitir que uma tarefa declare um `reply_schema` opcional no cabeçalho da mensagem, definindo o formato esperado da resposta.

#### Scenario: Mensagem com reply_schema
- **WHEN** `sac send <agente> "<corpo>"` é executado com flag `--schema <caminho-ou-json>`
- **THEN** o cabeçalho da mensagem contém `reply_schema` com a definição do schema
- **AND** o schema é armazenado como parte do arquivo .msg

#### Scenario: Mensagem sem reply_schema
- **WHEN** `sac send <agente> "<corpo>"` é executado sem `--schema`
- **THEN** a mensagem não contém `reply_schema` (comportamento atual, sem validação)

### Requirement: Validação de reply pelo daemon
O daemon SHALL validar a reply de um agente contra o `reply_schema` declarado na mensagem original, antes de entregá-la ao remetente.

#### Scenario: Reply válida
- **GIVEN** mensagem com `reply_schema: {"type": "object", "properties": {"veredito": {"enum": ["APROVADO", "REPROVADO"]}}}`
- **WHEN** o agente envia `sac send <sender> '{"veredito": "APROVADO"}'`
- **THEN** o daemon valida a reply contra o schema
- **AND** a reply é entregue ao remetente
- **AND** o evento `deliver` é registrado com `validation: ok`

#### Scenario: Reply inválida
- **GIVEN** mensagem com `reply_schema` (enum de vereditos)
- **WHEN** o agente envia `sac send <sender> '{"veredito": "INVALIDO"}'`
- **THEN** o daemon rejeita a reply
- **AND** a reply NÃO é entregue ao remetente
- **AND** o daemon devolve erro ao agente remetente com detalhes da violação do schema
- **AND** o evento `validation_error` é registrado em `log.jsonl`

#### Scenario: Reply sem schema não é validada
- **GIVEN** mensagem sem `reply_schema`
- **WHEN** o agente envia qualquer reply
- **THEN** a reply é entregue sem validação (comportamento atual)

### Requirement: Formato do schema
O sistema SHALL usar JSON Schema (draft-07) como formato de `reply_schema`, validado com a biblioteca `jsonschema` da stdlib ou fallback para validação manual minimalista (sem dependências externas).

#### Scenario: Schema JSON Schema válido
- **WHEN** um `reply_schema` JSON Schema é fornecido
- **THEN** o sistema o valida contra o meta-schema do JSON Schema draft-07
- **AND** se inválido, retorna erro ao remetente na criação da mensagem

#### Scenario: Schema inválido rejeitado
- **WHEN** `sac send --schema '{"type": "tipo_invalido"}' <agente> "<corpo>"` é executado
- **THEN** o sistema rejeita o envio com erro: "reply_schema inválido"
