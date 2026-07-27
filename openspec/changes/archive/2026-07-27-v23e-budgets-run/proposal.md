## Why

Uma run pode crescer indefinidamente: um agente em comportamento anômalo (reenvio automático, ping-pong de mensagens entre agentes) pode disparar centenas de mensagens sob o mesmo run_id sem nenhum controle. Como runs são criadas implicitamente por `sac send --run`, o enforce precisa acontecer no ponto de criação da mensagem e no daemon — não há nenhum executor interno onde embutir limites.

## What Changes

1. **Contadores por run**: tarefas (mensagens com o run_id), mensagens totais trocadas sob o run_id e wall time desde o `run_start` do journal.
2. **Tetos configuráveis**: campos `max_tasks_per_run`, `max_messages_per_run`, `max_wall_time_per_run` em `[session]` do `sac.toml` (0 = ilimitado, default).
3. **Enforce no `sac send` e no daemon**: antes de criar/entregar mensagem com run_id, os budgets da run são verificados; ao atingir um teto, a run é suspensa — novas mensagens rejeitadas com erro claro e evento `budget_exceeded` no log/journal.
4. **Overrides inline**: flags `--max-tasks`, `--max-messages`, `--max-wall-time` em `sac send --run` definem os budgets da run no momento da criação (primeira mensagem com o run_id), sobrescrevendo o sac.toml.
5. **Grace period de wall time**: tarefas claimed em andamento têm 30s para concluir após o teto de tempo.

## Non-goals

- Budgets de token/USD: o custo por token não é observável de forma harness-agnóstica (o SAC não sabe qual modelo cada harness usa nem quantos tokens cada chamada consome). Pi-extensible-workflows só consegue budgets de token porque é single-harness (OpenAI SDK fixo), condição que o SAC multi-harness não atende.
- Budgets globais (por sessão/estabelecimento) — apenas por run.
- Reintroduzir loops ou executor de tarefas (removidos na v26b).
- Mudanças em approval, reply_schema ou fan-out (outras partes da v23).

## Specs afetadas

- `budgets-run` (nova): tetos por run, enforce no send/daemon, grace period.
- `config` (delta): campos `max_tasks_per_run`, `max_messages_per_run`, `max_wall_time_per_run` em `[session]`.
- `cli` (delta): flags `--max-tasks`/`--max-messages`/`--max-wall-time` em `sac send --run`.

## Nota

Parte 5/5 da `v23-orquestracao-primitivas` fatiada. Pressupõe o modelo de run da parte 3/5 (`v23c-run-journal-resume`): budgets contam mensagens com `run_id` e usam o `run_start` do journal como referência de tempo. Baseline da suíte: 486 passed.
