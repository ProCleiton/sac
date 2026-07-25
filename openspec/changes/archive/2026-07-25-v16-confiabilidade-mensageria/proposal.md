## Why

O SAC foi usado intensivamente ao vivo em 24/07 na esteira CCB deste workspace,
e 4 bugs de mensageria foram observados com evidência direta:

1. **Reply não entregue ao leader** (3+ ocorrências): o agente conclui a tarefa,
   envia `sac send lead-coordinator "<resultado>"`, vê "mensagem enviada ✅", mas a
   resposta nunca chega à inbox do leader. O deliver_reply do daemon falha
   silenciosamente — a mensagem some ou vai para fila errada. Remédio manual:
   `sac inject lead-coordinator` + re-poke.
2. **done não limpa claimed (CRÍTICO, 3 ocorrências)**: o agente roda `sac done
   <id>`, vê "concluída ✅", mas o evento done não é registrado em `log.jsonl` e
   o arquivo `.msg` permanece em `.sac/claimed/<agente>/`. Efeito: a mensagem
   seguinte para o mesmo agente NÃO é entregue (fila travada), e o daemon fica
   re-pokeando a tarefa morta. Remédio manual: `mv claimed/<id>.msg done/`.
3. **Raiz de fila errada**: agente com cwd `/home/dev/Github` operou em
   `/home/dev/Github/sac/.sac` (repo do projeto SAC, que tem `.sac` próprio de
   sessão antiga) em vez de `/home/dev/Github/.sac`. A resolução da raiz da fila
   por descoberta de cwd é ambígua quando existem múltiplos `.sac/` na árvore.
4. **Poke não acorda o agente**: mensagem nova fica na inbox sem next — o daemon
   poke não dispara ação no harness. O agente fica "dormente" mesmo com `SAC:
   ...` no terminal. Remédio: `sac inject <agente>` re-injeta o prompt e destrava.
5. **Worker fala com o humano quando trava** (relato do usuário, 24/07): um
   worker perdeu permissão de commit na branch e, em vez de se reportar ao
   líder, fez a pergunta diretamente ao humano — quebrando a hierarquia e
   perdendo o fio da tarefa. O SAC não impõe hoje nenhuma regra de escalação:
   nada no protocolo diz que workers só se reportam ao líder, nem o daemon
   percebe que um worker está parado sem saber o que fazer.

## What Changes

- **deliver_reply com fallback/retry**: o daemon ao tentar deliver_reply de uma
  reply usa mecanismo mais robusto: (a) verifica se o destino é agente conhecido
  via `cfg.agent()` antes de tentar; (b) log de deliver inclui o id da mensagem
  no destino (cruzamento); (c) se o daemon não está ativo, o `sac send` cai no
  poke manual — garantir que o poke funcione para qualquer agente.
- **done com atomicidade (fsync + verificação pós-move)**: `Store.finish()` move
  o arquivo claimed→done com `shutil.move` + `fsync` no diretório destino.
  Após o move, verifica que o arquivo ORIGINAL não existe mais (claimed vazio).
  Se o move falhar, loga erro como `loop_error` e NÃO imprime "concluída ✅".
  Log done é escrito ANTES do move (write-ahead), não depois.
- **SAC_ROOT explícito**: variável de ambiente `SAC_ROOT` (ou `--sac-root` no
  CLI, ou campo `root` no `sac.toml` seção `[session]`) sobrescreve a descoberta
  automática por cwd. Se não definido, mantém o comportamento atual (cwd).
  `Store.__init__` recebe `root` explícito; todos os caminhos de fila usam
  `self.root` em vez de `Path.cwd() / ".sac"`.
- **Poke via tmux send-keys com Enter forçado**: o deliver do daemon adiciona
  um Enter extra (além do já existente) e usa `send-keys -t <pane> -l -- <text>`
  + `send-keys -t <pane> Enter` com pequeno delay (0.2s) entre o texto e o Enter.
  Em vez de apenas colar o corpo da mensagem, adiciona `"SAC: mensagem — rode
  \`sac next\`"` ao final, mesmo com o daemon ativo (redundância que destrava).
- **Protocolo de escalação padrão (worker → líder → humano)**: o SAC injeta um
  contrato de escalação em TODO prompt (boot e `sac inject`), independente do
  prompt_file do usuário: workers NUNCA falam com o humano — qualquer dúvida,
  erro, bloqueio ou falta de permissão é reportada ao líder via
  `sac send <líder>`; apenas o líder fala com o humano (`sac send user`).
  O nome real do líder vem de `cfg.leader`.
- **Poke com instrução de reporte**: o texto do poke do daemon passa a exigir
  reação — concluir com `sac done` OU, se estiver travado/sem saber como
  prosseguir, reportar a situação imediatamente ao líder.
- **Daemon escala ao líder após N pokes**: se uma mensagem claimed recebe
  `poke_escalate_after` pokes (config `[session]`, default 3) sem `done`, o
  daemon envia mensagem automática ao líder (sender `daemon`) relatando que o
  worker está sem progresso — o líder decide a recuperação. Escala uma única
  vez por mensagem; pokes continuam no teto do backoff.
- **Teste real ao vivo**: após o fix, submeter uma mensagem real de leader→dev-1
  e verificar entrega, reply de volta, e `sac done` com verificação de log e
  filesystem.

## Capabilities

### New Capabilities
- `protocolo-escalacao`: hierarquia worker → líder → humano injetada por padrão
  em todo agente; poke com instrução de reporte imediato; daemon escala ao
  líder workers sem progresso após N pokes.

### Modified Capabilities
- `core-mensageria`: deliver_reply com fallback/retry; done write-ahead + fsync +
  verificação pós-move; SAC_ROOT explícito; daemon poke com Enter forçado +
  instrução de reporte ao líder
- `config`: campo `root` opcional na seção `[session]`; campo
  `poke_escalate_after` (default 3)
- `sessao-tmux`: send-keys com delay + Enter extra + hint textual; injeção do
  contrato de escalação em todo prompt (boot e `sac inject`)

## Impact

**Código**: `sac/store.py` (finish() com atomicidade, root explícito), `sac/config.py`
(session.root, session.poke_escalate_after), `sac/daemon.py` (deliver_reply com
verificação, poke com Enter + reporte, escalonamento ao líder), `sac/commands.py`
(cmd_send com fallback, contrato de escalação no _inject_prompt, POKE_TEXT),
`sac/cli.py` (--sac-root). Templates: `prompts/dev.md`, `prompts/auditor.md`,
`prompts/leader.md` (regras de escalação).
Testes: `tests/test_store.py` (finish atomic, root resolve, done log antecipado),
`tests/test_daemon.py` (deliver_reply fallback, poke com Enter, escalonamento),
`tests/test_config.py` (session.root, poke_escalate_after),
`tests/test_commands.py` (contrato injetado com nome do líder).
Suíte atual: ~167 passed → alvo 195+.
