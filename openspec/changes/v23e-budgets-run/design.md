## Context

SAC pós-v26b: `cmd_run` e loops removidos; runs (parte 3/5, v23c) são agrupadores nomeados criados implicitamente por `sac send --run <id>`. Sem executor interno, o enforce de budgets precisa viver nos dois pontos por onde toda mensagem passa: o `sac send` (criação) e o daemon (entrega). Baseline da suíte: 486 passed.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0.

## Goals / Non-Goals

**Goals:**
- Tetos por run de tarefas, mensagens e wall time — só o que é harness-agnóstico
- Enforce no `sac send` e no daemon, com erro claro e evento `budget_exceeded`
- Default ilimitado (0), sem mudança de comportamento para quem não configurar

**Non-Goals:**
- Budgets de token/USD (ver D5)
- Budgets globais ou por agente
- Qualquer reintrodução de loops/executor

## Decisions

### D5. Budgets de tarefas/mensagens/tempo por run (NÃO token/USD, SEM loops)

**Problema**: runs podem crescer indefinidamente — um agente em comportamento anômalo pode disparar centenas de mensagens sob o mesmo run_id sem controle. O design original media budgets em "lançamentos de tarefas do loop"; com os loops removidos na v26b, os contadores precisam ser redefinidos sobre a mensageria.

**Escolha**: budgets por run de três dimensões observáveis de forma harness-agnóstica, redefinidos sem referência a loops:

1. **Tarefas**: mensagens criadas com o run_id (entradas `task_sent` do journal).
2. **Mensagens totais**: todas as mensagens trocadas sob o run_id (tarefas + replies correlacionadas).
3. **Wall time**: segundos desde o `run_start` do journal até agora.

Ao atingir qualquer teto, a run é **suspensa**: novas mensagens com o run_id são rejeitadas no `sac send` e bloqueadas no daemon; o journal registra `budget_exceeded` com a dimensão e o limite. Tarefas claimed em andamento têm grace period de 30s para concluir quando o teto é de wall time.

- **Por que não budgets de token/USD?**: o SAC é multi-harness — não sabe qual modelo (GPT, Claude, DeepSeek, Kimi, Ollama) cada harness usa, nem quantos tokens cada chamada consome. Pi-extensible-workflows só consegue budgets de token porque é single-harness (OpenAI SDK fixo). Para o SAC, budgets de token seriam (a) imprecisos (estimativa por caractere) ou (b) dependentes de harness (plugin por provedor) — inaceitável para um orquestrador agnóstico. Tarefas/mensagens/tempo são os substitutos harness-agnósticos.
- **Onde contar?**: o journal da run já registra `task_sent`/`task_done` com timestamps — os contadores são derivados do journal (fonte persistente), não de memória volátil. Isso elimina o problema de "contadores resetados no resume" do design original: após crash, o consumo é reconstruído lendo o journal.
- **Onde enforce?**: (a) `sac send --run` verifica os budgets antes de criar a mensagem — falha rápida para o remetente; (b) o daemon verifica na entrega — ponto tardio que cobre remetentes que não passam pelo CLI. Dois gates, mesma regra.
- **Overrides inline**: flags `--max-tasks`/`--max-messages`/`--max-wall-time` no primeiro `sac send --run <id>` (o que cria a run) definem os budgets da run, persistidos na entrada `run_start` do journal. Em mensagens seguintes da mesma run, as flags são ignoradas com aviso.

**Implementação**:
- `sac/budget.py`: `BudgetTracker` com `check_task()`, `check_message()`, `check_wall_time()`, `exceeded() -> str | None`, reconstruído a partir do journal da run.
- Config: `max_tasks_per_run`, `max_messages_per_run`, `max_wall_time_per_run` em `[session]`, validação `>= 0`, default 0 (ilimitado).
- Enforce em `cmd_send` (antes de criar o .msg) e no daemon (antes de entregar mensagem com run_id de run suspensa).
- Grace period: `threading.Timer` no daemon que, ao bater wall time, aguarda 30s antes de bloquear — claimed em andamento pode concluir.

**Testes**: `tests/test_budget.py` (teto de tarefas, de mensagens, wall time, ilimitado, grace period, reconstrução de contadores via journal, overrides inline).

## Risks / Trade-offs

- **[R1] Wall time depende do relógio do sistema**: ajustes de NTP podem distorcer o tempo decorrido. Como a referência é o timestamp do `run_start` no journal, usa-se `time.monotonic()` para o grace period em processo e timestamp de parede para o teto (teto aproximado é aceitável).
- **[R2] Replies de run suspensa**: replies a mensagens já entregues são aceitas durante o grace period; depois, são bloqueadas com `budget_exceeded`. O remetente recebe erro claro e pode reenviar sob outro run_id.
- **[R3] Dois gates podem divergir**: se o `sac send` passa mas o daemon bloqueia (teto atingido entre os dois), a mensagem fica na inbox da run suspensa. O resume (parte 3/5) reporta o estado; o operador decide.

## Riscos operacionais

Implementação em sessão direta de kimi-code, sem worktree dedicado nem esteira CCB:

1. Toda validação ao vivo acontece SOMENTE em diretórios descartáveis: `SAC_HOME`/`SAC_ROOT`/socket tmux apontando para `/tmp`, nunca contra a sessão viva.
2. Testes da suíte sempre com store em `tmp_path` do pytest.
3. Merge com a esteira parada (`sac down`). Rollback = `git checkout <commit-anterior>` + `sac up`.

## Rollback Plan

1. Reverter `sac/budget.py`, enforce no `sac send`/daemon e flags de budget.
2. Reverter campos de config `max_tasks_per_run`, `max_messages_per_run`, `max_wall_time_per_run`.
3. Com os campos ausentes, o comportamento volta ao default ilimitado — rollback sem efeito colateral.
