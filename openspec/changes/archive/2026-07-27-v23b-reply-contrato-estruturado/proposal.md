## Why

Hoje as replies dos agentes são texto livre — o líder precisa parsear manualmente e não há garantia de que a reply contém o campo esperado (ex.: veredito APROVADO/REPROVADO). Isso produz triagem manual e bugs recorrentes de interpretação. O contrato de reply precisa ser validado pelo daemon antes da entrega, transformando convenção de prompt em garantia de runtime.

## What Changes

1. **`reply_schema` opcional por tarefa**: a mensagem pode declarar um JSON Schema (draft-07, subconjunto minimalista) no cabeçalho via `sac send --schema <json>`. Sem schema, comportamento inalterado.
2. **Validação no daemon**: ao entregar a reply ao remetente, o daemon valida o corpo contra o `reply_schema` da mensagem original. Se inválida, a reply NÃO é entregue — o daemon devolve erro ao agente remetente com detalhes da violação e registra `validation_error` em `log.jsonl`.
3. **Validador stdlib**: `sac/reply_validator.py` com suporte a `type` (object/string/number/array), `properties`, `enum` e `required` — sem dependências externas.
4. **`reply_schema_default` no config**: campo opcional em `[session]` do `sac.toml`, aplicado a mensagens sem schema próprio.

## Non-goals

- JSON Schema completo (oneOf, allOf, pattern, format, $ref) — schemas fora do subconjunto são rejeitados com "schema não suportado".
- Validação obrigatória para todas as mensagens (schema é opt-in).
- Validação preliminar no `sac send` do agente (otimização futura; o daemon é o gatekeeper).
- Mudanças em approval, runs, fan-out ou budgets (outras partes da v23).

## Specs afetadas

- `reply-contrato-estruturado` (nova): reply_schema declarado por tarefa, validação pelo daemon, formato do schema.
- `cli` (delta): flag `--schema` em `sac send`.
- `config` (delta): campo `reply_schema_default` em `[session]`.
- `core-mensageria` (delta): reply_schema no cabeçalho; validação de reply no daemon; reply-to-sender com validação.

## Nota

Parte 2/5 da `v23-orquestracao-primitivas` fatiada. Independente das demais partes; baseline da suíte: 486 passed.
