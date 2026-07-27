## Context

SAC pós-v26b. Sem suporte a paralelismo: o líder dispara mensagens uma a uma e correlaciona replies manualmente. Esta change adiciona fan-out com coleta agregada. Baseline da suíte: 486 passed.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0.

## Goals / Non-Goals

**Goals:**
- Disparo do mesmo template para N agentes com um comando
- Coleta chaveada de replies com agregado entregue ao solicitante
- Timeout configurável com agregado parcial

**Non-Goals:**
- Fan-out bloqueante no CLI
- Síntese/agregação semântica das replies
- Coleta automática sem daemon

## Decisions

### D4. Fan-out com coleta em arquivo temporário

**Problema**: o líder precisa disparar o mesmo template para N agentes e receber um agregado, sem correlacionar N replies manualmente.

**Escolha**: `sac fanout <template> <targets...>` cria N mensagens com cabeçalho `fanout_id` comum. O daemon coleta as replies em um agregado (`.sac/fanout/<fanout_id>.json`) e o entrega ao solicitante quando todos respondem ou o timeout expira.

- **Alternativa A**: `sac fanout` bloqueia até todas as replies. Rejeitado porque o CLI do SAC não pode bloquear (o harness precisa processar outras tarefas). A coleta é assíncrona, feita pelo daemon.
- **Alternativa B**: cada reply entregue individualmente. Rejeitado porque o líder teria que correlacionar N replies manualmente — o valor do fan-out é o agregado.
- **Por que arquivo agregado e não mensagem inline?**: o agregado pode ser grande (N replies de revisão). Ele é montado em disco e enviado como corpo de uma mensagem .msg ao solicitante.

**Implementação**:
- `sac/fanout.py`: `FanOutManager` (cria mensagens com `fanout_id`, agenda timeout) e `FanOutCollector` (coleta replies, monta agregado).
- O agente responde normalmente; a reply carrega `reply_to_fanout: <id>` no cabeçalho (propagado da mensagem original).
- O daemon, ao processar reply com `reply_to_fanout`, encaminha ao FanOutCollector em vez do deliver_reply convencional.
- Quando todos responderam ou o timeout expirou, o agregado JSON (`{agente: reply, ...}`) é enviado como mensagem ao solicitante.
- Timeout: `threading.Timer` no daemon, agendado na criação do fan-out.
- Resiliência: agregado parcial persistido em `.sac/fanout/<id>.partial.json` a cada reply; no restart do daemon, fan-outs pendentes são retomados com novo timeout.

**Testes**: `tests/test_fanout.py` (fan-out básico, coleta completa, coleta parcial com timeout, sem replies, agregado bem formado, daemon morto).

## Risks / Trade-offs

- **[R1] Timeout em thread pode perder replies**: se o daemon morre entre a coleta parcial e o timeout, as replies acumuladas em memória seriam perdidas. Mitigação: `.partial.json` persistido a cada reply + retomada de fan-outs pendentes no boot do daemon.
- **[R2] Fan-out requer daemon ativo**: sem daemon, `sac fanout` cria as mensagens mas não coleta automaticamente. O solicitante coleta manualmente com `sac recv` de cada agente. Documentado no help do comando.
- **[R3] Agregado grande no pane**: o agregado é entregue como mensagem normal — replies muito longas podem poluir o pane do solicitante. Aceitável; o arquivo `.sac/fanout/<id>.json` permanece disponível para consulta.

## Riscos operacionais

Implementação em sessão direta de kimi-code, sem worktree dedicado nem esteira CCB:

1. Toda validação ao vivo acontece SOMENTE em diretórios descartáveis: `SAC_HOME`/`SAC_ROOT`/socket tmux apontando para `/tmp`, nunca contra a sessão viva.
2. Testes da suíte sempre com store em `tmp_path` do pytest.
3. Merge com a esteira parada (`sac down`). Rollback = `git checkout <commit-anterior>` + `sac up`.

## Rollback Plan

1. Reverter `sac/fanout.py`, `sac fanout` e a coleta de fan-out no daemon.
2. Arquivos `.sac/fanout/` órfãos são inertes — removíveis manualmente.
3. Mensagens com `fanout_id` viram mensagens comuns (campo ignorado) após o rollback.
