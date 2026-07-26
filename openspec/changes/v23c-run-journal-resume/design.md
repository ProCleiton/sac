## Context

SAC pós-v26b: o comando `sac run` e os loops foram REMOVIDOS (change v26b-remove-loops). Não existe mais nenhum executor interno de sequências de tarefas — toda tarefa é uma mensagem enviada via `sac send`. Sem esse executor, perdeu-se também a única noção de "sequência de trabalho": se o daemon ou um agente morre no meio, nada registra o que já foi concluído. Esta change reintroduz o conceito de run **sem reintroduzir o executor**: run é um agrupador nomeado de mensagens com journal e resume. Baseline da suíte: 486 passed.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0.

## Goals / Non-Goals

**Goals:**
- Run como agrupador nomeado de mensagens via campo `run` no cabeçalho
- Journal append-only por run, com fsync, sobrevivendo a crash
- `sac runs` para visibilidade de status por run
- `sac resume <id>` que re-entrega mensagens não concluídas (pending + claimed órfãs) sem re-executar done

**Non-Goals:**
- Reintroduzir `sac run`/loops (removidos na v26b)
- Ordenação ou dependências entre tarefas da run
- Executor interno de qualquer tipo — a run é passiva (agrupador + journal)

## Decisions

### D2. Run como agrupador nomeado sobre a mensageria existente (redesign pós-v26b)

**Problema**: o design original (pré-v26b) acopla runs ao `cmd_run`, que não existe mais. Como ter runs (agrupamento + journal + resume) sem executor de tarefas?

**Escolha**: a run é criada implicitamente pela primeira mensagem que carrega um run_id. `sac send <agente> "<tarefa>" --run <id>` grava `run: <id>` no cabeçalho do .msg; se `.sac/runs/<id>/` não existe, é criado com `journal.jsonl` e a entrada `run_start`. A partir daí, toda mensagem com esse run_id registra `task_sent`, e todo `sac done` de mensagem da run registra `task_done`. `sac resume <id>` re-entrega o que não está done.

- **Alternativa A**: comando `sac run` criando a run explicitamente. Rejeitado — seria reintroduzir pela porta dos fundos o comando removido na v26b. A run não precisa de cerimônia de criação: o primeiro envio a define.
- **Alternativa B**: checkpoint em banco SQLite. Rejeitado porque adiciona dependência externa — o SAC é stdlib-only (a memória de longo prazo usa SQLite via stdlib, mas o journal precisa ser append-only de texto para inspeção manual e tolerância a truncamento).
- **Alternativa C**: estado mutável (JSON sobrescrito com contadores). Rejeitado — append-only evita corrupção por escrita parcial: se o processo morre durante o append, a linha mal-formada é ignorada na leitura (a última entrada válida é o checkpoint real).
- **Por que filesystem?**: a mensageria já é filesystem-based com write-ahead log + fsync (desde a v16). Runs usam o mesmo padrão, sem dependências novas.

**Modelo de resume**: `sac resume <id>` NÃO executa tarefas — ele reconcilia o estado da fila com o journal:

1. Lê o journal e identifica as mensagens da run com `task_sent` sem `task_done` correspondente.
2. Para cada uma: se está `pending` (inbox, nunca claimed), re-injeta o poke no pane do agente (ou deixa para o daemon entregar); se está `claimed` órfã (claimed há mais de `poke_stale_after` sem done — agente/daemon morreu), move de volta para `inbox/<agente>/` para re-entrega.
3. Mensagens com `task_done` no journal nunca são tocadas.
4. Se todas as mensagens da run estão done, informa que a run está concluída.

**Implementação**:
- `sac/run.py`: classe `RunJournal` com `ensure(run_id)` (cria dir + `run_start` se ausente), `log_entry()`, `read_entries()` (tolera última linha mal-formada), `pending_messages()`, `is_complete()`.
- `cmd_send`: flag `--run <id>` → grava `run: <id>` no cabeçalho, chama `RunJournal.ensure()` e registra `task_sent`.
- `Store.finish()`: se a mensagem concluída tem `run` no cabeçalho, registra `task_done` no journal após o move bem-sucedido.
- `cmd_runs`: lista `.sac/runs/*/` com contagens (sent/done/pending) derivadas do journal.
- `cmd_resume`: reconciliação descrita acima.
- Parsing de cabeçalho aceita o campo `run` sem quebrar mensagens existentes (ausente = sem run).

**Testes**: `tests/test_run.py` (create implícita, append, fsync, truncado, resume pending, resume claimed órfã, resume de run completa, run inexistente).

## Risks / Trade-offs

- **[R1] Overlap journal × log.jsonl**: ambos registram eventos de tarefas. O journal é específico da run (checkpoint para resume, leitura sequencial rápida); log.jsonl é o audit trail completo. O overlap é intencional.
- **[R2] Run órfã de mensagens sem run_id**: mensagens sem `--run` não entram em nenhum journal — comportamento atual inalterado. Runs são opt-in.
- **[R3] Resume é reconciliação, não re-execução**: `sac resume` não garante ordem nem re-executa nada — apenas re-entrega o que a fila perdeu. Quem decide reenviar tarefas novas é o líder.
- **[R4] Claimed órfã × claimed legítima**: uma mensagem claimed há muito tempo pode ser um agente lento, não morto. O resume usa `poke_stale_after` como heurística e registra cada requeue em `log.jsonl` para auditoria.

## Riscos operacionais

Implementação em sessão direta de kimi-code, sem worktree dedicado nem esteira CCB:

1. Toda validação ao vivo acontece SOMENTE em diretórios descartáveis: `SAC_HOME`/`SAC_ROOT`/socket tmux apontando para `/tmp`, nunca contra a sessão viva.
2. Testes da suíte sempre com store em `tmp_path` do pytest.
3. Merge com a esteira parada (`sac down`). Rollback = `git checkout <commit-anterior>` + `sac up`.

## Rollback Plan

1. Reverter `sac resume`, `sac runs` e a flag `--run` em `sac send`.
2. Reverter `sac/run.py` e o hook de `task_done` em `Store.finish()`.
3. Diretórios `.sac/runs/` órfãos são inertes — podem ser removidos manualmente.
