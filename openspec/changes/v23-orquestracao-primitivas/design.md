## Context

SAC v1.22 está em andamento (change v22-ux-iniciante-doctor). O workflow atual depende de disciplina de prompt: cada agente "sabe" que deve responder com formato estruturado, chamar `sac done`, não enviar reply sem deliver_reply. Isso produz bugs recorrentes (reply sem deliver_reply, race done/send, triagem manual de vereditos). A v23 transforma garantias de convenção em garantias de runtime, inspirada pela extensão pi-extensible-workflows (orquestração multi-agente determinística) mas mantendo o diferencial do SAC: multi-harness, panes tmux visíveis, papéis persistentes, mensageria filesystem.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0. Suíte atual: ~294 passed.

## Goals / Non-Goals

**Goals:**
- Approval como primitiva do daemon com máquina de estado (pending→approved/rejected)
- Run com journal e resume após crash (sem re-executar tarefas concluídas)
- Reply estruturado validado pelo daemon antes da entrega (contrato parseável)
- Fan-out paralelo com coleta chaveada de replies
- Budgets por run (tarefas, mensagens, wall time) — só o que é harness-agnóstico

**Non-Goals:**
- Budgets de token/USD (custo por token não é observável de forma harness-agnóstica; pi-extensible-workflows só consegue porque é single-harness)
- Sub-agentes in-process (manter arquitetura atual com harnesses externos)
- Trocar o transporte (manter mensageria em arquivos, não IPC/Redis/pubsub)
- Quebrar compatibilidade com os 8 prompts de papéis atuais (leader, dev-1, dev-2, docs, auditor, secops, revisor, deployment)
- Enxugada dos prompts (follow-up depois das primitivas)

## Decisions

### D1. Approval como novo tipo de mensagem, não novo comando de sistema

**Problema**: o SAC precisa de um mecanismo para leader solicitar aprovação ao user e aguardar resposta (aprovado/rejeitado) antes de prosseguir. Hoje isso é feito informalmente — o leader pergunta ao user via mensagem e o user responde, mas não há garantia de que a resposta será parseável.

**Escolha**: criar um novo tipo de mensagem `approval_request` com cabeçalho `type` no .msg e campo `state: pending|approved|rejected`. Os comandos `sac approve <id>` e `sac respond <id> <veredito>` alteram o estado e disparam reply automática ao leader.

- **Alternativa A**: estado global em memória do daemon. Rejeitado porque o daemon pode morrer — o estado precisa ser persistente.
- **Alternativa B**: arquivo separado `.sac/approvals/`. Rejeitado porque adiciona complexidade de gerenciamento de outro diretório — a mensagem já carrega o estado, e o fluxo inbox→claimed→done cobre o lifecycle.
- **Por que usar o mesmo mecanismo de mensageria?**: reusa store, log, daemon delivery, stale detection. A única diferença é que o tipo `approval_request` tem semântica de estado que o daemon reconhece e as replies são automáticas (não precisam de `sac send` manual).

**Implementação**:
- Adicionar campo `type` ao cabeçalho do .msg (vazio ou ausente = mensagem normal, `approval_request` = solicitação de aprovação).
- Adicionar campo `state` ao cabeçalho: `pending` (inbox/claimed), `approved` ou `rejected` (done).
- `sac approve <id>`: busca a mensagem em claimed ou done do sender, muda state para `approved`, registra log, envia reply automática.
- `sac respond <id> <veredito> [motivo]`: mesmo fluxo com veredito configurável.
- Daemon: ao detectar approval_request na inbox do user, entrega no pane do leader (não no user — user não tem pane). Na verdade: approval_request vai para `inbox/user/` mas o daemon entrega no pane do leader também.
- **Correção**: approval_request é enviada pelo leader à inbox do user. O daemon, ao ver uma approval_request, entrega no pane do leader (não do user) — pois o user não tem pane. O leader vê o pedido e responde com `sac approve` ou `sac respond`. A reply vai automaticamente ao leader.

**Testes**: `tests/test_checkpoint.py` (approve, respond, estado, duplicata).

### D2. Run journal sobre a mensageria existente

**Problema**: tarefas são independentes — se o daemon morre no meio de uma sequência, não há como saber o que já foi concluído. O SAC precisa de um mecanismo de "run" que agrupe tarefas e permita resume após crash.

**Escolha**: runs são diretórios em `.sac/runs/<run_id>/` com `journal.jsonl` append-only. Cada `sac done` de uma tarefa pertencente a uma run registra checkpoint no journal. `sac resume <run_id>` lê o journal e avança para a próxima tarefa.

- **Alternativa A**: checkpoint em banco SQLite. Rejeitado porque adiciona dependência externa — o SAC é stdlib-only.
- **Alternativa B**: variável de ambiente para rastrear estado. Rejeitado porque não sobrevive a crash do daemon.
- **Por que filesystem?**: a mensageria já é filesystem-based com write-ahead log + fsync (desde a v16). Runs usam o mesmo padrão: journal append-only com fsync, sem dependências novas.
- **Por que journal e não estado mutável?**: append-only evita corrupção por escrita parcial — se o processo morre durante o append, a linha mal-formada é ignorada no resume (última entrada válida é o checkpoint real). Estado mutável (ex.: JSON sobrescrito) pode ficar inconsistente.

**Implementação**:
- `sac/run.py`: classe `RunJournal` com `log_entry()`, `read_checkpoint()`, `next_pending_task()`, `is_complete()`.
- A run é criada em `cmd_run` (existente) — expandir para criar o diretório `.sac/runs/<id>/` e escrever `run_start`.
- `Store.finish()` aceita `run_id` opcional. Se presente, chama `RunJournal.log_entry()` após o move bem-sucedido.
- `sac resume <run_id>`: `RunJournal.from_id(run_id)` → `next_pending_task()` → envia a próxima mensagem.

**Testes**: `tests/test_run.py` (journal append, fsync, resume, resume com journal truncado, resume de run completa).

### D3. Reply schema validado pelo daemon com fallback para sem validação

**Problema**: hoje as replies são texto livre — o leader precisa parsear manualmente. Não há garantia de que a reply contém o campo esperado (ex.: veredito APROVADO/REPROVADO). Isso produz bugs de triagem manual.

**Escolha**: a mensagem pode opcionalmente declarar um `reply_schema` (JSON Schema draft-07) no cabeçalho. O daemon valida a reply contra o schema antes de entregar ao remetente. Sem schema, comportamento inalterado.

- **Alternativa A**: schema obrigatório para todas as mensagens. Rejeitado porque quebra compatibilidade com mensagens existentes e aumenta a barreira de adoção.
- **Alternativa B**: schema no config global. Rejeitado porque nem toda tarefa precisa do mesmo formato de reply — schema por tarefa é mais flexível.
- **Por que JSON Schema?**: é um padrão amplamente conhecido, parsável por qualquer linguagem. A implementação no SAC usa validação manual minimalista (stdlib) para evitar dependências externas — apenas tipos básicos (object, string, number, array, enum) e required fields.
- **Por que validação no daemon e não no `sac send` do agente?**: o daemon é o gatekeeper central — se a validação é no `sac send`, um harness que não usa `sac send` (ex.: script customizado) pode pular a validação.

**Implementação**:
- `sac/reply_validator.py`: classe `ReplyValidator` com `validate(reply_body: str, schema: dict) -> (bool, errors[])`.
- Suporte inicial: `type` (object/string/number/array), `properties` com `type` e `enum`, `required`. Sem referências (`$ref`) externas.
- Daemon: ao detectar reply na inbox do remetente, verifica se a mensagem original tem `reply_schema`. Se sim, valida antes de deliver_reply. Se inválida, envia erro ao agente remetente.
- O erro inclui detalhes: "campo 'veredito' deve ser um dos valores: APROVADO, REPROVADO; recebido: 'INVALIDO'".

**Testes**: `tests/test_reply_validator.py` (schema válido, inválido, sem schema, schema complexo, schema com required).

### D4. Fan-out com coleta em arquivo temporário

**Problema**: o SAC não tem suporte a paralelismo — o leader precisa enviar mensagens uma a uma e coletar replies manualmente. Fan-out permite disparar o mesmo template para N agentes e receber um agregado.

**Escolha**: `sac fanout <template> <targets...>` cria N mensagens com cabeçalho `fanout_id` comum. O daemon coleta as replies em um agregado (arquivo `.sac/fanout/<fanout_id>.json`) e entrega ao solicitante quando todos respondem ou o timeout expira.

- **Alternativa A**: o comando `sac fanout` bloqueia até todas as replies. Rejeitado porque o CLI do SAC não pode bloquear (o harness precisa processar outras tarefas). A coleta é assíncrona, feita pelo daemon.
- **Alternativa B**: cada reply é individual. Rejeitado porque o leader teria que correlacionar N replies manualmente — o valor do fan-out é o agregado.
- **Por que arquivo agregado e não mensagem inline?**: o agregado pode ser grande (N replies de revisão de código). Uma mensagem .msg com o agregado inline é o mecanismo de entrega — mas o agregado é montado em disco e enviado como corpo de mensagem.

**Implementação**:
- `sac/fanout.py`: classes `FanOutManager` (cria mensagens, gerencia timeout), `FanOutCollector` (coleta replies, monta agregado).
- `sac send` sem daemon envia reply normalmente. O daemon, ao processar reply com `reply_to_fanout`, encaminha ao FanOutCollector.
- Quando todos responderam ou timeout expirou, o FanOutCollector monta o agregado JSON (`{agente: reply, ...}`) e envia como mensagem ao solicitante.
- Timeout: implementado com `threading.Timer` no daemon. Ao criar o fan-out, agenda o callback de timeout.

**Testes**: `tests/test_fanout.py` (fan-out básico, coleta parcial com timeout, fan-out sem replies, agregado bem formado).

### D5. Budgets de tarefas/mensagens/tempo (NÃO token/USD)

**Problema**: runs podem crescer indefinidamente — um loop mal configurado ou um agente que entra em loop infinito pode disparar centenas de tarefas sem controle.

**Escolha**: budgets por run de três dimensões observáveis de forma harness-agnóstica: tarefas lançadas, mensagens trocadas e tempo de parede (wall clock). Budgets de token/USD estão **explicitamente fora de escopo**.

- **Por que não budgets de token/USD?**: o SAC é multi-harness — não sabe qual modelo (GPT-4, Claude, DeepSeek, Kimi, Ollama) cada harness está usando, nem quantos tokens cada chamada consume. Pi-extensible-workflows só consegue budgets de token porque é single-harness (OpenAI SDK fixo). Para o SAC, budgets de token seriam ou (a) imprecisos (estimar por caractere) ou (b) dependentes de harness (plugin específico para cada provedor). Nenhum dos dois é aceitável para um orquestrador agnóstico.
- **Por que tarefas/mensagens/tempo?**: são contadores que o SAC pode observar diretamente: (a) tarefas = `sac run` + cada iteração do loop; (b) mensagens = arquivos .msg criados; (c) tempo = timestamp do run_start vs agora. Todos sem depender do harness.
- **O que acontece ao atingir o teto?**: a run é suspensa (novas tarefas rejeitadas, novas mensagens bloqueadas). Tarefas claimed em andamento têm grace period de 30s para concluir. O journal registra `budget_exceeded` com a dimensão e o limite.

**Implementação**:
- `sac/budget.py`: classe `BudgetTracker` com `check_task() -> bool`, `check_message() -> bool`, `check_wall_time() -> bool`, `exceeded() -> str | None`.
- Contadores em memória (resetados a cada resume). O journal tem a entrada de checkpoint para reconstrução aproximada.
- Enforce: no `sac send` e `sac run`, antes de criar a mensagem, verificar budgets da run ativa via `BudgetTracker.check_*()`.
- Grace period: `threading.Timer` no daemon que, ao bater wall time, aguarda 30s antes de bloquear novas tarefas.

**Testes**: `tests/test_budget.py` (task budget excedido, message budget, wall time, grace period, resume após budget, budget ilimitado).

### D6. Validação de reply no daemon — não no `sac send`

**Problema**: onde validar a reply? No `sac send` do agente remetente ou no daemon ao entregar?

**Escolha**: validação no daemon, no momento da entrega. O `sac send` do agente envia a reply como texto livre (comportamento atual). O daemon, ao processar a reply, lê o schema da mensagem original e valida.

- **Motivo**: um harness pode usar ferramentas que chamam `sac send` diretamente, ou o agente pode usar scripts que geram a reply sem passar pelo validador do CLI. A validação no daemon é o ponto de verificação mais tardio — garante que nenhuma reply inválida chega ao destinatário, independente de como foi enviada.
- **Trade-off**: o agente só descobre que a reply foi rejeitada quando o daemon entrega o erro. Para feedback mais rápido, o `sac send` poderia fazer uma validação preliminar (otimização futura).

## Risks / Trade-offs

- **[R1] Approval adiciona estado ao .msg**: mensagens existentes sem `type` continuam funcionando. Mensagens com `type: approval_request` não quebram consumidores antigos (que ignoram campos extras).
- **[R2] Journal de run tem overlap com log.jsonl**: ambos registram eventos de tarefas. O journal é específico da run (checkpoint para resume), enquanto log.jsonl é audit trail completo. O overlap é intencional — o journal é otimizado para resume (leitura sequencial rápida), o log para auditoria (consulta por timestamp).
- **[R3] Fan-out com timeout em thread pode perder replies**: se o daemon morre entre a coleta parcial e o timeout, as replies acumuladas são perdidas. Mitigação: persistir o agregado parcial em `.sac/fanout/<id>.partial.json` a cada reply recebida. No resume do daemon, fan-outs pendentes são retomados (com novo timeout).
- **[R4] Budget de wall time depende de relógio do sistema**: se o relógio é ajustado (NTP, mudança manual), o tempo decorrido pode ser incorreto. `monotonic()` da stdlib mitiga parcialmente (não é afetado por NTP, mas sim por suspensão do sistema). Aceitável — é um teto aproximado.
- **[R5] Schema JSON sem dependências**: a implementação manual do validador cobre apenas os casos de uso esperados (object, string, enum, required). Schemas complexos (oneOf, allOf, pattern, format) serão rejeitados com erro "schema não suportado" em vez de validados. Se a demanda crescer, adicionar `jsonschema` ou `fastjsonschema` como dependência opcional.
- **[R6] Fan-out requer daemon ativo**: a coleta de replies e o timeout dependem do daemon em execução. Sem daemon, fan-out cria as mensagens mas não coleta replies automaticamente. O solicitante pode coletar manualmente com `sac recv` de cada agente. Documentado no help do comando.
- **[R7] Budgets não são persisted no journal da run**: após um crash, os contadores de budget são perdidos. No resume, os budgets são resetados — a run pode exceder os tetos originais. Mitigação: registrar o consumo acumulado no journal como entrada `budget_snapshot` a cada checkpoint.
- **[R8] Aprovação: leader envia, daemon entrega no leader**: o fluxo de approval_request é contra-intuitivo — o leader envia uma mensagem para `inbox/user/` (destino virtual), mas o daemon entrega no pane do leader (não do user). Isso porque o user não tem pane tmux. A documentação do comando `sac send --approval` deve esclarecer esse comportamento.

## Riscos operacionais do dogfooding

Riscos específicos de implementar esta change no mesmo repositório que roda a esteira SAC viva (dogfooding), acordados com o usuário:

1. **Acoplamento pipx editable**: o CLI `sac` serve o working tree do repo. O daemon em memória é seguro (código carregado no início), mas toda chamada de CLI (`send`, `next`, `sidebar`, `status --mini`) executa o código do working tree no momento — estado intermediário quebrado (ex.: syntax error, import ausente) derruba a mensageria da esteira viva.
2. **Categoria de maior risco**: esta change mexe no núcleo de mensageria (store, daemon, parsing de .msg, delivery pipeline). É a de maior risco desde a v16.
3. **Mitigações obrigatórias** (devem constar nas tasks):
   - Implementação em **worktree git dedicado** (`git worktree add ../sac-dev v23-orquestracao-primitivas`), mantendo o working tree principal estável até o merge.
   - Builds de dev testados SOMENTE contra `SAC_ROOT`/`SAC_CONFIG`/socket descartáveis (diretório temp), nunca contra o estado da sessão viva.
   - Merge programado com a esteira **parada** (`sac down`). Rollback = `git checkout` do commit anterior + `sac up`.
4. **Recomendação**: o ciclo de implementação deve ser orquestrado preferencialmente pela esteira **CCB** (independente da ferramenta em obras), para que o SAC não precise coordenar a própria cirurgia. A decisão final é do usuário no gate de aprovação.
5. **Testes da suíte**: sempre com store em diretório temporário (`tmp_path` do pytest), nunca contra `~/.sac-esteira` ou qualquer sessão ativa.

## Rollback Plan

1. **Approval**: reverter novos comandos `sac approve`, `sac respond`, flag `--approval` em `sac send`. Reverter estado `approval` no parsing de mensagens.
2. **Run journal**: reverter `sac/run.py`, reverter `Store.finish()` (remover parâmetro run_id), reverter `sac resume`.
3. **Reply schema**: reverter `sac/reply_validator.py`, reverter validação no daemon, reverter flag `--schema`.
4. **Fan-out**: reverter `sac/fanout.py`, reverter `sac fanout`, reverter coleta de fan-out no daemon.
5. **Budgets**: reverter `sac/budget.py`, reverter campos de config, reverter enforce no daemon e `sac send`.
6. **Config**: reverter campos `max_tasks_per_run`, `max_messages_per_run`, `max_wall_time_per_run`, `reply_schema_default`.
7. Cada passo é independente — pode ser revertido isoladamente sem afetar os demais.
