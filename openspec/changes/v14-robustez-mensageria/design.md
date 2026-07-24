## Context

SAC v1.3 foi arquivada com specs oficiais. Observações ao vivo e follow-ups
dos gates revelaram 5 fragilidades + 2 chores. A v1.4 endereça todas sem
introduzir novas capacidades — são modificações em specs existentes.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0 (testes com pytest). Suíte: 117 passed.

## Goals / Non-Goals

**Goals:**
- boot_wait configurável por agente (opencode mais lento, kimi mais rápido)
- Eliminar stale pokes falsos para respostas lidas via `sac next`
- `sac log -f` não morrer no boot sem log.jsonl
- Re-check pré-poke para evitar race condition cosmético
- `status --clean` com dry-run obrigatório antes da execução
- Remover PNGs da mascote descartada do tracking
- Commitar uv.lock para reprodutibilidade

**Non-Goals:**
- Não alterar o contrato `SAC_DONE` / `sac done`
- Não modificar o fluxo de entrega do daemon (entrega direta via paste)
- Não adicionar novos comandos (apenas flags)
- Não incluir novo mascote (decisão posterior do usuário)

## Decisions

### D1. boot_wait: per-agent override + default 8s

- **Escolha**: `AgentConfig.boot_wait: float | None = None` (None = herda do
  global). `Config.boot_wait` default muda de 3 para 8. `cmd_up` usa o valor
  específico do agente em vez do global no `time.sleep()` pré-injeção.
- **Alternativas**:
  - Só aumentar o global para 8: penaliza kimi (3s seria suficiente).
  - Retry de injeção: polling no pane até detectar prompt do harness —
    complexo, frágil (cada harness tem prompt diferente).
  - Boot_wait no [[agents]] via campo extra: simples, flexível, sem quebra
    de compatibilidade (None = fallback).
- **Motivo**: flexibilidade sem breaking change. Quem não definir `boot_wait`
  no agente herda o global (agora 8s). Kimi pode usar 3, opencode 12.

### D2. Reply marking — distinção reply vs tarefa no envio

**Problema descoberto no teste real**: o auto-ack do `sac next` (primeira versão)
cobria o caminho manual, mas o caminho DOMINANTE é a entrega pelo daemon — e o
daemon trata toda mensagem como tarefa (claimed + stale-poke). Uma resposta de
dev-1 para leader chegava via daemon, ia para claimed/leader, e o daemon
disparava stale-pokes a cada 10s até o leader rodar `sac done` numa mensagem
que era só informacional. Observado ao vivo: 3 pokes enfileirados.

**Raiz**: mensagem não tem tipo — o sistema não distingue "tarefa" de "resposta".

- **Escolha**: `store.send(sender, to, body)` infere reply_to automaticamente
  no momento do envio. Se o sender tem exatamente 1 mensagem claimed cujo
  remetente original é o destinatário `to`, a nova mensagem é marcada
  `reply_to=<id_da_tarefa>`. O campo é persistido no arquivo `.msg` como
  cabeçalho. Mensagens sem reply_to = tarefas. Mensagens antigas sem o campo
  são tratadas como tarefas (compatível).
- **Implementação**:
  - `Message.reply_to: str | None = None` no dataclass.
  - `Store._parse()` extrai `reply_to` do cabeçalho (ou None se ausente).
  - `Store.send()`: após gerar o ID, verifica claimed do sender; se exatamente
    1 claimed cujo `from` == `recipient`, seta reply_to.
  - `Daemon._deliver_next()`: após `store.next()` + paste, se `msg.reply_to`,
    chama `store.finish_reply(agent, msg.id)` (move claimed→done, log
    "deliver_reply"). Reply nunca fica em claimed por mais de ~100ms.
  - `cmd_next()` (legado): após `store.next()`, se `msg.reply_to`, chama
    `store.finish_reply(agent, msg.id)` — reply auto-ackada ao ser lida.
    O método `store.ack()` da primeira versão é mantido para consistência
    (daemon active → CLI ack), mas replies são cobertos pelo finish_reply.
- **Validação contra o código**:
  - A claim do sender é o estado mais preciso: se dev-1 tem uma tarefa
    claimed de leader e envia algo de volta, é uma reply. Se tem múltiplas
    claimed, não marca (caso raro: dev-1 recebeu 2 tarefas e está respondendo
    à 1ª — sem reply_to, tratada como tarefa, seguro).
  - `Daemon._process_agent()`: com reply_to, msg sai de claimed em <100ms.
    O stale-check no topo do loop não a encontra. Correto.
  - `notify_sweep()`: idem — msg sai de claimed antes do próximo sweep.
  - Compatibilidade: mensagens existentes sem reply_to têm `reply_to = None`
    → tratadas como tarefas (sem mudança semântica).
- **Por que a versão anterior (auto-ack no next) passou no gate e o teste real
  pegou?**: A validação do gate foi puramente estática (revisão de código). O
  auto-ack no `sac next` de fato funciona para o caminho manual. Mas no uso
  real o daemon entrega a maioria das mensagens — e o daemon não passa pelo
  `cmd_next`. O reply marking corrige no ponto de origem (envio), antes da
  entrega, e é respeitado tanto pelo daemon quanto pelo CLI.
- **Alternativas**:
  - Comparar sender do `from` no destino (quem recebe verifica se a msg veio
    de um agente que está lhe devolvendo resultado). Mais complexo, requer
    consulta ao store do destinatário no momento da leitura.
  - Sempre auto-done após entrega do daemon: eliminaria o claimed para tarefas
    reais também, quebrando o lembrete de `sac done`.
  - Dois comandos (`sac reply`, `sac task`): complexidade cognitiva e quebra
    de contrato nos prompts.

### D3. log -f wait no boot

- **Escolha**: no `cmd_log`, se `follow=True` e o arquivo não existe, entra
  em loop `while not path.is_file(): time.sleep(0.5)`.
- **Alternativa**: criar `log.jsonl` vazio no `cmd_up`. Mais simples mas polui
  o filesystem mesmo sem eventos.
- **Motivo**: o loop é simples, não cria arquivo artificial, e o sleep de 0.5s
  é imperceptível no boot. O daemon escreve o 1º evento (PID) em <1s.

### D4. Re-check pré-poke (cosmético)

- **Escolha**: em `notify_sweep`, após obter `stale` IDs, re-consultar
  `store.claimed(agent)` antes de cada poke. Se o ID não está mais em claimed,
  não pokear.
- **Motivo**: 2 linhas, elimina race window de ~100ms entre detecção e envio.
  Custo desprezível (já tem o loop de agentes).

### D5. status --clean com dry-run

- **Escolha**: `store.clean_orphans()` ganha parâmetro `dry_run: bool =
  False` (False mantém compatibilidade). O CLI `sac status --clean` chama com
  `dry_run=True` por padrão; `--clean --yes` chama com `dry_run=False`.
- **Alternativa**: confirmação interativa (`input("Confirma? [y/N]")`).
  Incompatível com automação/scripts.
- **Motivo**: flag `--yes` é automation-friendly e mais seguro que
  confirmação interativa. O dry-run padrão é o mais conservador.

### D6. PNGs: git rm tracking

- **Escolha**: `git rm docs/logo-candidates/*.png docs/sac-mascot.png`.
  Os PNGs saem do tracking mas o histórico os preserva. Sem quebra de
  compatibilidade (ninguém depende deles).
- **Motivo**: mascote descartada pelo usuário. Manter no tracking é lixo.

### D7. uv.lock: commitar

- **Escolha**: `git add uv.lock`. O lockfile garante instalações
  reproduzíveis para quem usa `uv`.
- **Alternativa**: adicionar ao `.gitignore`. Justificativa: uv.lock é
  gerado automaticamente pelo `uv lock` — se o projeto não usa `uv` como
  ferramenta de build oficial, o lockfile pode ficar desatualizado.
  No entanto, o `pyproject.toml` já declara as dependências (stdlib zero),
  então o uv.lock é essencialmente vazio (só metadados do Python). Commitar
  é inofensivo e útil para consistência.
- **Recomendação**: commitar. O uv.lock é pequeno e versiona a resolução
  do Python ≥ 3.11 para `uv run`.

### D8. Reply cut queue — entrega imediata mesmo com claimed

- **Escolha**: no `Daemon._process_agent()`, mesmo quando há tarefa claimed,
  verificar se o agente tem pending reply (`store.peek_next()` retorna
  `(id, reply_to)`). Se sim, entregar via `_deliver_next()` (que faz
  next+paste+finish_reply).
- **Implementação**: novo método `Store.peek_next(agent) -> tuple[str, str | None] | None`
  que retorna (id, reply_to) do próximo pending sem consumir. No daemon:
  após o stale handling, se `peek_next` mostra reply, chama `_deliver_next(name)`.
  O `_deliver_next` já faz finish_reply para replies, e o claimed+stale
  handling continua funcionando para tarefas.
- **Segurança**: o harness enfileira o input de forma segura (observado com
  pokes — múltiplos pokes acumulam e o harness processa em ordem). Entregar
  uma reply enquanto o agente trabalha não causa perda — o agente vê a reply
  no terminal após terminar o turno atual.
- **Alternativa**: criar fila paralela de replies sem usar claimed. Mais
  complexo, não resolve problema real (harness enfileira de qualquer forma).
- **Motivo**: 27s observados de espera por causa da serialização. Reply não
  precisa de `sac done` — furar a fila é seguro.

### D9. Rota para user (sac send user)

- **Escolha**: `cmd_send` aceita `to == "user"` sem validar via `cfg.agent()`.
  A mensagem vai para `inbox/user/`. Sem daemon (não há pane do user), sem
  poke. Leitura via `sac log` (ou `SAC_AGENT=user sac next`).
- **Implementação**: em `cmd_send`, `if to != "user": cfg.agent(to)`.
  A store já cria diretório `inbox/user/` sob demanda em `store.send()`.
- **Motivo**: o auditor desviou resposta pelo leader (+1 turno de LLM) porque
  `sac send user` falhava com ConfigError. User não precisa de pane — a
  mensagem está no filesystem, acessível via log.

### D10. Backoff exponencial de poke

- **Escolha**: por mensagem claimed, o intervalo entre pokes dobra a cada
  tentativa (base `poke_stale_after`, teto 5 min). Estado em memória do
  daemon (`dict[str, dict[str, float]]`: agent → msg_id → last_poke_time).
  Reinício do daemon reseta o estado (aceitável).
- **Implementação daemon**: `Daemon._poke_state: dict[str, dict[str, float]]`
  armazena `{msg_id: last_poke}`. Novo método `_poke_interval(msg_id)`
  calcula: `min(poke_stale_after * 2**n, 300)` onde n = número de pokes
  já enviados para esta msg. O `_process_agent` usa `time.monotonic()` e
  o estado para decidir se poka.
- **notify_sweep legado**: aplicar o mesmo backoff. `cmd_notify` recebe um
  dict opcional de estado; `notify_sweep` aceita `poke_state=None`.
  Se None, mantém comportamento atual (sem backoff). Se dict, usa backoff.
  Legado raramente usado (daemon é o caminho principal); backoff no legado
  é trivial e não quebra nada.
- **Alternativa**: manter legado sem backoff. Motivo para aplicar: o código
  do backoff é pequeno (5 linhas no loop), e o legado é usado exatamente
  quando o daemon está offline (cenário de fallback onde backoff é útil).
- **Motivo**: 4 pokes em 40s no auditor ao vivo — cada um custa um turno de
  LLM. Backoff reduz impacto sem perder o lembrete.

## Risks / Trade-offs

- **[R1] Reply marking condicional (exatamente 1 claimed)**: se dev-1 tem 2
  tarefas claimed (ex.: de leader e de auditor) e responde a leader, o reply_to
  não é inferido (2 claimed, condição exata falha). A resposta cai como tarefa
  → claimed + stale poke. Mitigação: caso raro no fluxo normal (reply-to-sender
  ocorre antes de `sac done`, então o sender tem exatamente 1 claimed). Se
  ocorrer, o usuário faz `sac done` manual como antes. Melhoria futura possível
  (match por sender mais sofisticado).
- **[R2] boot_wait global 3→8**: para sessões onde todos os agentes são
  kimi (rápidos), o boot fica 5s mais lento. Mitigação: definir
  `boot_wait=3` explicito em `[session]` ou `boot_wait=3` por agente.
  O default 8 é conservador para o caso mais comum (opencode + kimi misto).
- **[R3] dry-run no clean_orphans**: scripts existentes que chamam
  `sac status --clean` esperando remoção efetiva vão parar de funcionar
  (precisam adicionar `--yes`). **BREAKING** leve. Mitigação:
  documentar na release; erro claro se `--clean` sem `--yes` for usado em
  script (ex.: "Use --yes to confirm").
- **[R4] Reply cut queue pode entregar reply durante execução de comando
  crítico**: o harness recebe o paste no buffer de input. Se o agente está
  no meio de um comando sensível (ex.: `git commit --amend`), o paste pode
  contaminar o input. Mitigação: o mesmo risco existe com pokes (observado
  e aceito). O harness enfileira e processa em ordem. Em cenários reais com
  kimi/opencode, o input é sempre interpretado após o prompt do LLM — seguro.
- **[R5] Backoff de poke em memória**: reinício do daemon reseta todos os
  contadores, podendo gerar pokes imediatos ao religar. Mitigação: aceitável
  — o daemon reinicia com o início da sessão; o 1º poke após reinício não
  causa dano (é o mesmo que o comportamento atual).

## Open Questions

Nenhuma (itens 1-10 decididos na proposta).

## Rollback Plan

1. **boot_wait**: reverter default para 3; remover campo `boot_wait` do
   AgentConfig. Sem migração.
2. **Reply marking**: reverter `store.send()` (remover inferência de reply_to),
   reverter `daemon._deliver_next()` (remover finish_reply), reverter
   `cmd_next` (sempre next ou ack, sem finish_reply). Mensagens já com
   reply_to no arquivo são tratadas como tarefas (campo ignorado se o código
   de reply for revertido).
3. **log -f wait**: reverter loop de wait (volta a imprimir "log vazio").
4. **Re-check**: reverter (2 linhas).
5. **dry-run clean**: remover flags `--yes`/`--dry-run`, restaurar
   comportamento destrutivo direto. Sem migração de dados.
6. **PNGs**: `git restore --staged` ou `git rm --cached` revertido via
   `git checkout HEAD -- <files>`. Não afeta dados.
7. **uv.lock**: `git rm --cached uv.lock` + `.gitignore` se necessário.
8. **Reply cut queue**: reverter `Daemon._process_agent()` (remover
   `_deliver_pending_reply`). Sem migração.
9. **Rota user**: reverter `cmd_send` (volta a validar cfg.agent(to) sempre).
   Mensagens em inbox/user/ permanecem (inofensivas).
10. **Backoff**: remover `_poke_state` do daemon e parâmetro de `notify_sweep`.
    O comportamento volta a usar `notify_interval` fixo.
