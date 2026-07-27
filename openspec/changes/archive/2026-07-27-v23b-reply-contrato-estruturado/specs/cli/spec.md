## ADDED Requirements

### Requirement: Flag --schema no comando send
O comando send SHALL aceitar a flag `--schema <json>` para declarar o reply_schema esperado da tarefa.

#### Scenario: send com schema
- **WHEN** `sac send dev-1 "Valide a config" --schema '{"type": "object", "properties": {"veredito": {"enum": ["OK", "FAIL"]}}}'` é executado
- **THEN** a mensagem é criada com `reply_schema` no cabeçalho

#### Scenario: send com schema mal-formado
- **WHEN** `sac send dev-1 "tarefa" --schema 'não-é-json'` é executado
- **THEN** o sistema rejeita o envio com erro: "reply_schema inválido"
