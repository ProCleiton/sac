## Why

O workflow do SAC hoje depende de disciplina de prompt: cada agente "sabe" que deve responder com formato estruturado, que deve chamar `sac done` após concluir, que não deve enviar reply sem deliver_reply. Isso produz bugs recorrentes (reply sem deliver_reply, race done/send, triagem manual de vereditos, worker travado sem recuperação) porque a garantia é de convenção, não de runtime. A mudança proposta inspira-se na extensão pi-extensible-workflows (orquestração multi-agente determinística) mas adapta ao diferencial do SAC: multi-harness, panes tmux visíveis, papéis persistentes, mensageria filesystem.

## What Changes

1. **Checkpoint/aprovação como primitiva do daemon**: novo tipo de mensagem `approval_request` com máquina de estado `pending → approved/rejected`. Comandos CLI `sac approve <id>` e `sac respond <id> <veredito>`. Rota obrigatória leader↔user: o leader envia approval_request ao user, o user responde, o daemon entrega o veredito ao leader.
2. **Run com journal e resume**: conceito de "run" agrupando tarefas com status (pending/running/done/failed). O journal é append-only no `.sac/runs/`. O daemon persiste checkpoint a cada tarefa concluída. `sac resume <run>` retoma a run de onde parou sem re-executar tarefas concluídas.
3. **Contrato de reply estruturado**: toda tarefa declara um `reply_schema` (ex.: `{"type": "object", "properties": {"veredito": {"enum": ["APROVADO", "REPROVADO"]}}}`). O daemon valida a reply contra o schema antes de entregar ao remetente. Se inválida, devolve erro ao remetente com detalhes da violação.
4. **Fan-out paralelo**: comando `sac fanout <template> <targets...>` que dispara o mesmo template para N agentes simultaneamente, coleta replies chaveadas por agente, e entrega o agregado ao solicitante.
5. **Budgets por run (LIMITADO)**: tetos configuráveis de lançamentos de tarefas, mensagens e tempo de parede por run. Quando um teto é atingido, a run é pausada/suspensa com erro claro. **Não** inclui budgets de token/USD (ver design para justificativa).

## Capabilities

### New Capabilities
- `checkpoint-aprovacao`: mensagem approval_request, máquina de estado pending→approved/rejected, comandos CLI sac approve/sac respond, rota leader↔user
- `run-journal-resume`: runs agrupando tarefas, journal append-only, checkpoint em .sac/runs/, comando sac resume
- `reply-contrato-estruturado`: reply_schema declarado por tarefa, validação pelo daemon antes da entrega, devolução de erro ao remetente se inválido
- `fan-out-paralelo`: comando sac fanout, disparo simultâneo para N agentes, coleta chaveada de replies, agregado ao solicitante
- `budgets-run`: tetos por run de tarefas lançadas, mensagens trocadas e tempo de parede; pausa/suspensão da run ao atingir teto

### Modified Capabilities
- `core-mensageria`: aprovação como estado de mensagem (além de pending/claimed/done); reply_schema validado; fan-out como novo fluxo de mensageria
- `cli`: novos comandos sac approve, sac respond, sac resume, sac fanout; sac run expandido
- `config`: novos campos em [session] para budgets (max_tasks_per_run, max_messages_per_run, max_wall_time_per_run) e schema de reply

## Impact

- Código novo: `sac/checkpoint.py`, `sac/run.py`, `sac/reply_validator.py`, `sac/fanout.py`, `sac/budget.py`
- Código modificado: `sac/daemon.py` (validação de reply, approval_request, budgets, fan-out), `sac/store.py` (run journal, checkpoint de run), `sac/cli.py` (novos comandos), `sac/commands.py` (lógica dos comandos), `sac/config.py` (novos campos de config)
- Testes novos em `tests/test_checkpoint.py`, `tests/test_run.py`, `tests/test_reply_validator.py`, `tests/test_fanout.py`, `tests/test_budget.py`
- Suíte atual: ~294 passed → alvo 340+.
- Compatibilidade: sem quebra. Runs são opt-in (sem run, comportamento idêntico ao atual). Reply_schema é opcional (sem schema, validação não é aplicada). Fan-out e approval_request são comandos novos.
- Specs: `checkpoint-aprovacao`, `run-journal-resume`, `reply-contrato-estruturado`, `fan-out-paralelo`, `budgets-run` (novas); `core-mensageria`, `cli`, `config` (delta).
