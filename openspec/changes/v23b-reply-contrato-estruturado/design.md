## Context

SAC pós-v26b. Replies são texto livre e o líder faz triagem manual de vereditos. Esta change adiciona contrato de reply validado pelo daemon. Baseline da suíte: 486 passed.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0.

## Goals / Non-Goals

**Goals:**
- Reply estruturado validado pelo daemon antes da entrega (contrato parseável)
- Schema opt-in por tarefa (sem quebra de compatibilidade)
- Erro de validação acionável devolvido ao agente remetente

**Non-Goals:**
- JSON Schema completo (subconjunto minimalista stdlib)
- Schema obrigatório global
- Validação preliminar no `sac send` (otimização futura)

## Decisions

### D3. Reply schema validado pelo daemon com fallback para sem validação

**Problema**: hoje as replies são texto livre — não há garantia de que a reply contém o campo esperado (ex.: veredito APROVADO/REPROVADO), produzindo triagem manual.

**Escolha**: a mensagem pode opcionalmente declarar um `reply_schema` (JSON Schema draft-07, subconjunto) no cabeçalho. O daemon valida a reply contra o schema antes de entregar ao remetente. Sem schema, comportamento inalterado.

- **Alternativa A**: schema obrigatório para todas as mensagens. Rejeitado porque quebra compatibilidade e aumenta a barreira de adoção.
- **Alternativa B**: schema apenas no config global. Rejeitado porque nem toda tarefa precisa do mesmo formato — schema por tarefa é mais flexível (o config global existe como default opcional, não como única fonte).
- **Por que JSON Schema?**: padrão amplamente conhecido e parseável. A implementação no SAC usa validação manual minimalista (stdlib) — apenas `type` (object/string/number/array), `properties`, `enum` e `required`. Sem `$ref` externas.
- **Por que validação no daemon e não no `sac send` do agente?**: o daemon é o gatekeeper central — se a validação fosse no `sac send`, um harness que não usa o CLI (script customizado) poderia pular a validação.

**Implementação**:
- `sac/reply_validator.py`: classe `ReplyValidator` com `validate(reply_body: str, schema: dict) -> (bool, errors[])`.
- Daemon: ao detectar reply na inbox do remetente, lê o `reply_schema` da mensagem original. Se presente, valida antes do deliver_reply. Se inválida, envia erro ao agente remetente com detalhes: "campo 'veredito' deve ser um dos valores: APROVADO, REPROVADO; recebido: 'INVALIDO'".
- `sac send --schema <json>`: rejeita envio se o schema é mal-formado ou fora do subconjunto suportado.
- Config: `reply_schema_default` em `[session]` aplicado quando a mensagem não declara schema próprio.

**Testes**: `tests/test_reply_validator.py` (válido, inválido, sem schema, enum, required, complexo) + integração no daemon.

### D6. Validação de reply no daemon — não no `sac send`

**Problema**: onde validar a reply? No `sac send` do agente remetente ou no daemon ao entregar?

**Escolha**: validação no daemon, no momento da entrega. O `sac send` do agente envia a reply como texto livre (comportamento atual). O daemon, ao processar a reply, lê o schema da mensagem original e valida.

- **Motivo**: um harness pode usar ferramentas que chamam `sac send` diretamente, ou scripts que geram a reply sem passar pelo CLI. A validação no daemon é o ponto de verificação mais tardio — garante que nenhuma reply inválida chega ao destinatário, independente de como foi enviada.
- **Trade-off**: o agente só descobre a rejeição quando o daemon devolve o erro. Validação preliminar no `sac send` é otimização futura.

## Risks / Trade-offs

- **[R1] Schema JSON sem dependências**: o validador manual cobre apenas os casos esperados (object, string, number, array, enum, required). Schemas complexos (oneOf, allOf, pattern, format) são rejeitados com erro "schema não suportado" em vez de validados. Se a demanda crescer, adicionar `jsonschema`/`fastjsonschema` como dependência opcional.
- **[R2] Reply inválida trava o fluxo?**: não — a reply rejeitada não é entregue, mas o erro devolvido ao agente permite reenvio corrigido. A mensagem original não é afetada.

## Riscos operacionais

Implementação em sessão direta de kimi-code, sem worktree dedicado nem esteira CCB:

1. Toda validação ao vivo acontece SOMENTE em diretórios descartáveis: `SAC_HOME`/`SAC_ROOT`/socket tmux apontando para `/tmp`, nunca contra a sessão viva.
2. Testes da suíte sempre com store em `tmp_path` do pytest.
3. Merge com a esteira parada (`sac down`). Rollback = `git checkout <commit-anterior>` + `sac up`.

## Rollback Plan

1. Reverter `sac/reply_validator.py` e a validação no daemon.
2. Reverter flag `--schema` em `sac send` e campo `reply_schema_default` no config.
3. Mensagens sem schema nunca são afetadas — rollback sem impacto em fluxos legados.
