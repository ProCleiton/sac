## ADDED Requirements

### Requirement: Configuração de reply_schema global
O sistema SHALL aceitar um campo `reply_schema_default` opcional na seção `[session]` do `sac.toml`, aplicado a todas as mensagens que não declarem schema próprio.

#### Scenario: reply_schema_default configurado
- **GIVEN** `[session]` contém `reply_schema_default = '{"type": "object", "properties": {"status": {"enum": ["OK", "FAIL"]}}}'`
- **WHEN** `sac send dev-1 "tarefa"` é executado sem --schema
- **THEN** a mensagem usa o schema default da config

#### Scenario: Sem reply_schema_default
- **GIVEN** `[session]` sem `reply_schema_default`
- **WHEN** `sac send dev-1 "tarefa"` é executado sem --schema
- **THEN** a mensagem não tem reply_schema (sem validação)

#### Scenario: reply_schema_default inválido
- **GIVEN** `[session]` com `reply_schema_default` mal-formado ou fora do subconjunto suportado
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro indicando o campo inválido
