## Why

Observações do uso real ao vivo e follow-ups dos gates da v1.3 revelaram 5
fragilidades operacionais: (1) boot_wait global de 3s engole prompt do opencode;
(2) respostas lidas via `sac next` ficam claimed para sempre, gerando stale pokes
falsos; (3) `sac log -f` morre no boot se log.jsonl não existe; (4) race de poke
pós-done (cosmético); (5) `status --clean` é destrutivo sem dry-run. Além disso,
o repo tem PNGs órfãos da mascote descartada e uv.lock sem tratamento.

## What Changes

- **boot_wait por agente**: `[[agents]]` ganha campo `boot_wait` opcional que
  sobrescreve o global `[session].boot_wait` para aquele agente. Permite
  opencode com wait maior sem penalizar kimi. Default global vira 8 (de 3).
- **Auto-ack condicional com reply marking**: todo mensagem enviada via `sac send`
  tem reply_to inferido automaticamente: se o sender tem exatamente 1 tarefa
  claimed cujo remetente original é o destinatário, a nova mensagem é marcada
  reply_to=<id_da_tarefa>. O daemon entrega replies sem exigir `sac done` (move
  direto para done/ após o paste, log "deliver_reply"). No modo legado (sem
  daemon), `sac next` auto-acka replies ao lê-las. Mensagens sem reply_to
  (= tarefas) seguem a semântica claimed+done inalterada. Compatível com
  mensagens antigas (sem o campo, tratadas como tarefas).
- **`sac log -f` resiliente no boot**: com follow, aguarda o arquivo
  `log.jsonl` aparecer (loop com sleep) em vez de retornar "log vazio" e
  morrer.
- **Re-check pré-poke**: em `notify_sweep`, antes de enviar o poke, re-verificar
  claimed para evitar poke obsoleto se o agente fez `sac done` entre a detecção
  e o envio. Correção simples de 2 linhas. Baixa prioridade.
- **`status --clean` com dry-run**: `--dry-run` (lista órfãos sem remover) é o
  padrão quando `--clean` sozinho; `--clean --yes` executa a remoção. A flag
  `--clean` existente passa a ser dry-run por segurança.
- **Chore: PNGs**: `git rm docs/logo-candidates/*.png docs/sac-mascot.png`.
- **Chore: uv.lock**: commitar (reprodutibilidade de ambiente).
- **Resposta fura a fila**: no daemon, mensagem com reply_to é entregue mesmo
  com tarefa claimed em andamento (prioridade sobre tarefas serializadas).
  Usa peek + next para não consumir tarefas acidentalmente.
- **Rota para user**: `sac send user "<msg>"` é aceito sem validação de agente.
  Mensagem vai para `inbox/user/` (sem deliver/poke). Leitura via `sac log`.
- **Backoff exponencial de poke**: intervalo dobra a cada poke à mesma mensagem
  (base `poke_stale_after`, teto 5 min). Estado em memória do daemon.
  Aplicado também ao `notify_sweep` legado (dict compartilhado por referência).

## Capabilities

### New Capabilities
Nenhuma — todas são modificações em specs existentes.

### Modified Capabilities
- `config`: campo `boot_wait` por agente ([[agents]] boot_wait=N)
- `core-mensageria`: reply_to + reply cut queue + backoff de poke + rota user;
  log -f espera arquivo no boot
- `cli`: `sac send user` aceito; status --clean ganha dry-run/--yes; log -f não
  morre sem arquivo
- `orphan-cleanup`: dry-run por padrão, --yes para executar

## Impact

**Código**: `sac/config.py` (AgentConfig.boot_wait), `sac/store.py`
(`reply_to` em send, `peek_next()`, `ack()`, `clean_orphans()` com dry-run),
`sac/commands.py` (cmd_next e cmd_send com reply/user, cmd_log, cmd_status,
notify_sweep re-check + backoff), `sac/cli.py` (--yes flag), `sac/daemon.py`
(deliver_reply, reply cut queue, backoff).
Testes: `tests/test_config.py`, `tests/test_store.py`,
`tests/test_commands.py`. PNGs removidos e `.gitignore`/`.gitattributes`
se necessário. `uv.lock` adicionado ao tracking.
