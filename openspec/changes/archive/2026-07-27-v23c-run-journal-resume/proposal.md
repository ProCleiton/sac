## Why

Tarefas no SAC são independentes entre si — se o daemon ou um agente morre no meio de uma sequência de trabalho, não há como saber o que já foi concluído nem o que ficou órfão. A v26b removeu o `cmd_run` e os loops (que executavam tarefas sequenciais internamente); o que falta é um conceito minimalista de "run" como **agrupador nomeado de mensagens**, com journal append-only para auditoria e resume de mensagens não concluídas — sem reintroduzir nenhum executor de tarefas.

## What Changes

1. **Run como agrupador nomeado**: nova flag `sac send <agente> "<tarefa>" --run <id>` grava `run: <id>` no cabeçalho da mensagem. A primeira mensagem com um run_id cria `.sac/runs/<id>/journal.jsonl` com a entrada `run_start`. Não existe comando `sac run` — a run nasce implicitamente do primeiro envio.
2. **Journal append-only**: `.sac/runs/<id>/journal.jsonl` registra `run_start`, `task_sent` (por mensagem com run_id), `task_done` (por `sac done` de mensagem da run), com fsync a cada entrada. Linha final mal-formada (crash durante append) é ignorada na leitura.
3. **`sac runs`**: lista as runs conhecidas com status agregado (pending/claimed/done por run).
4. **`sac resume <id>`**: re-entrega as mensagens da run que não estão done — pending (nunca entregues) e claimed órfãs (agente/daemon morto antes do `sac done`) voltam para a inbox do agente. Mensagens done nunca são re-executadas.

## Non-goals

- Reintroduzir `sac run` ou qualquer executor/loop de tarefas (removidos na v26b — a run é só agrupador + journal + resume de mensageria).
- Orquestração de ordem/dependência entre tarefas da run (o líder decide o que envia e quando).
- Budgets por run (parte 5/5 — v23e-budgets-run).
- Mudanças em approval, reply_schema ou fan-out (outras partes da v23).

## Specs afetadas

- `run-journal-resume` (nova): run como agrupador via run_id, journal append-only, `sac runs`, `sac resume`.
- `cli` (delta): flag `--run` em `sac send`; comandos `sac runs` e `sac resume`.
- `core-mensageria` (delta): campo `run` no cabeçalho da mensagem; checkpoint de `task_done` no journal.

## Nota

Parte 3/5 da `v23-orquestracao-primitivas` fatiada. Independente das demais partes; baseline da suíte: 486 passed.
