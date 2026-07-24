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
- **Teste real ao vivo**: após o fix, submeter uma mensagem real de leader→dev-1
  e verificar entrega, reply de volta, e `sac done` com verificação de log e
  filesystem.

## Capabilities

### New Capabilities
Nenhuma — todas são correções em specs existentes.

### Modified Capabilities
- `core-mensageria`: deliver_reply com fallback/retry; done write-ahead + fsync +
  verificação pós-move; SAC_ROOT explícito; daemon poke com Enter forçado
- `config`: campo `root` opcional na seção `[session]`
- `sessao-tmux`: send-keys com delay + Enter extra + hint textual

## Impact

**Código**: `sac/store.py` (finish() com atomicidade, root explícito), `sac/config.py`
(AgentConfig.root? / session.root), `sac/daemon.py` (deliver_reply com verificação,
poke com Enter), `sac/commands.py` (cmd_send com fallback), `sac/cli.py` (--sac-root).
Testes: `tests/test_store.py` (finish atomic, root resolve, done log antecipado),
`tests/test_daemon.py` (deliver_reply fallback, poke com Enter),
`tests/test_config.py` (session.root). Suíte atual: ~167 passed → alvo 180+.
