## Context

SAC pós-v26b (loops e `cmd_run` removidos). O workflow atual não tem aprovação como primitiva: o líder pergunta ao usuário via mensagem comum e a resposta é texto livre, sem garantia de formato. Esta change transforma a aprovação em garantia de runtime. Baseline da suíte: 486 passed.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0.

## Goals / Non-Goals

**Goals:**
- Approval como primitiva do daemon com máquina de estado (pending → approved/rejected)
- Comandos `sac approve` / `sac respond` utilizáveis de qualquer pane
- Reply automática ao líder com o veredito (sem `sac send` manual do usuário)
- Compatibilidade total com mensagens legadas (sem `type`)

**Non-Goals:**
- Painel/UX dedicado de aprovações
- Aprovação por múltiplos usuários ou quórum
- Mudanças em outros fluxos de mensageria (reply_schema, fan-out, runs — outras partes da v23)

## Decisions

### D1. Approval como novo tipo de mensagem, não novo comando de sistema

**Problema**: o SAC precisa de um mecanismo para o líder solicitar aprovação ao usuário e aguardar resposta parseável (aprovado/rejeitado) antes de prosseguir. Hoje isso é informal — texto livre sem garantia de runtime.

**Escolha**: novo tipo de mensagem `approval_request` com campos `type` e `state` no cabeçalho do .msg (`pending | approved | rejected`). Os comandos `sac approve <id>` e `sac respond <id> <veredito> [motivo]` alteram o estado e disparam reply automática ao líder.

- **Alternativa A**: estado global em memória do daemon. Rejeitado porque o daemon pode morrer — o estado precisa ser persistente.
- **Alternativa B**: arquivo separado `.sac/approvals/`. Rejeitado porque adiciona gerenciamento de outro diretório — a mensagem já carrega o estado, e o fluxo inbox → done cobre o lifecycle.
- **Por que o mesmo mecanismo de mensageria?**: reusa store, log, delivery do daemon e stale detection. A única diferença é que `approval_request` tem semântica de estado reconhecida pelo daemon e as replies são automáticas.

**Fluxo completo (coerente, sem contradição):**

1. O líder executa `sac send user "<contexto do pedido>" --approval`. A mensagem é criada em `inbox/user/` com `type: approval_request` e `state: pending`.
2. O `user` é um destino virtual — **não tem pane tmux próprio**. O usuário humano acompanha a sessão "cavalgando" o pane do líder (via `sac attach`).
3. O daemon, ao detectar uma approval_request na inbox do user, **renderiza o pedido no pane do líder** (texto do pedido + id + instrução de como responder). A mensagem permanece na inbox do user até ser respondida.
4. O usuário lê o pedido no pane do líder e responde **de qualquer pane** (qualquer diretório com acesso ao SAC_ROOT):
   - `sac approve <id>` → estado `approved`;
   - `sac respond <id> REJECTED ["motivo"]` → estado `rejected` (também aceita `APPROVED`).
5. O comando grava o estado no .msg, move a mensagem para `done/user/` e registra o evento `approval` em `log.jsonl`.
6. Uma **reply automática** é enviada ao líder (`from: user`, `reply_to` da approval_request) com o veredito e o motivo — o daemon a entrega no pane do líder pelo fluxo normal de deliver_reply.

**Implementação**:
- Campo `type` opcional no cabeçalho do .msg (ausente/vazio = mensagem normal).
- Campo `state` no cabeçalho: `pending` (inbox), `approved`/`rejected` (done).
- `Store.is_approval_request()`, `Store.set_approval_state()`.
- `cmd_approve` / `cmd_respond` em commands.py; flag `--approval` em `cmd_send` com validação de role (apenas leader).
- Daemon: ao varrer `inbox/user/`, approval_requests são renderizadas no pane do líder em vez de procurar um pane "user".

**Testes**: `tests/test_checkpoint.py` (approve, respond, estado, duplicata, render no pane do líder).

## Risks / Trade-offs

- **[R1] Approval adiciona estado ao .msg**: mensagens existentes sem `type` continuam funcionando. Consumidores antigos ignoram campos extras.
- **[R2] Fluxo contra-intuitivo (líder envia, daemon entrega no líder)**: a approval_request vai para `inbox/user/` (destino virtual), mas é renderizada no pane do líder porque o user não tem pane. O help de `sac send --approval` deve esclarecer esse comportamento.
- **[R3] Resposta fora de pane da sessão**: `sac approve`/`sac respond` funcionam de qualquer diretório com acesso ao SAC_ROOT — não dependem de tmux. Se o daemon estiver parado, o estado é gravado mesmo assim e a reply ao líder é entregue quando o daemon voltar.

## Riscos operacionais

Implementação em sessão direta de kimi-code, sem worktree dedicado nem esteira CCB:

1. Toda validação ao vivo acontece SOMENTE em diretórios descartáveis: `SAC_HOME`/`SAC_ROOT`/socket tmux apontando para `/tmp`, nunca contra a sessão viva.
2. Testes da suíte sempre com store em `tmp_path` do pytest.
3. Merge com a esteira parada (`sac down`). Rollback = `git checkout <commit-anterior>` + `sac up`.

## Rollback Plan

1. Reverter comandos `sac approve`, `sac respond` e flag `--approval` em `sac send`.
2. Reverter campos `type`/`state` no parsing de mensagens e a renderização de approval_request no daemon.
3. Cada passo é independente; mensagens legadas não são afetadas em nenhum estágio.
