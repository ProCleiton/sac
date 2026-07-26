## Why

O SAC não tem suporte a paralelismo: para obter a mesma revisão de N agentes, o líder envia N mensagens uma a uma e correlaciona N replies manualmente. Fan-out transforma esse padrão recorrente (ex.: "revise este PR" para dev + auditor + secops) em um único comando com coleta agregada e chaveada por agente.

## What Changes

1. **Comando `sac fanout <template> <targets...>`**: dispara o mesmo template para N agentes simultaneamente; cada mensagem carrega `fanout_id` comum no cabeçalho.
2. **Coleta chaveada pelo daemon**: replies com `reply_to_fanout` são coletadas em `.sac/fanout/<fanout_id>.json`; quando todos respondem (ou o timeout expira), o agregado `{"agente": "reply", ...}` é entregue ao solicitante como mensagem única.
3. **Timeout configurável**: flag `--timeout <segundos>` (default 600s); no timeout, o agregado parcial é entregue com `"<agente>": "TIMEOUT"` nos ausentes.
4. **Resiliência a crash**: agregado parcial persistido em `.sac/fanout/<id>.partial.json` a cada reply recebida.

## Non-goals

- Fan-out bloqueante no CLI (a coleta é assíncrona, feita pelo daemon).
- Coleta sem daemon (sem daemon, as mensagens são criadas mas a coleta é manual via `sac recv` — documentado no help).
- Agregação inteligente/semântica das replies (o agregado é um mapa chaveado, sem síntese).
- Mudanças em approval, reply_schema, runs ou budgets (outras partes da v23).

## Specs afetadas

- `fan-out-paralelo` (nova): comando fanout, coleta chaveada, timeout.
- `cli` (delta): comando `sac fanout`.
- `core-mensageria` (delta): mensagens com `fanout_id`/`reply_to_fanout`; daemon gerencia coleta.

## Nota

Parte 4/5 da `v23-orquestracao-primitivas` fatiada. Independente das demais partes; baseline da suíte: 486 passed.
