## Why

A sidebar v2 e o status bar da v17 aproximaram o SAC do layout do CCB, mas
faltam refinamentos para fechar a paridade visual e informativa:

- A árvore windows→agentes não tem **divisão visual de subníveis** (conectores
  de árvore) nem mostra o **modelo** de cada agente (só o comando `kimi`/
  `opencode`).
- Não há **contadores** (mensagens pendentes por agente) nem **tempo ocioso**
  desde o último evento — informação que o CCB dá de relance.
- O rodapé carrega dicas estáticas desnecessárias (`Copy: MouseDrag Paste:
  S-C-v Focus: C-b o`) e não mostra sessão/window nem resumo do estado dos
  agentes.

## What Changes

- **Sidebar v3 — árvore com conectores**: agentes renderizados com `├─`/`└─`
  sob cada window, substituindo a indentação simples.
- **Modelo por agente**: extraído de `--model <valor>` nos `args` do agente
  (prefixo de alias como `esteira/` removido) e exibido ao lado do comando —
  ex.: `kimi/k3`. Sem `--model`, mostra só o comando.
- **Badge de inbox**: `(N)` com a contagem de arquivos em `inbox/<agente>/`
  quando N > 0.
- **Tempo ocioso**: `· <idade>` (ex.: `5m`, `1h`) desde o último evento do
  agente no `log.jsonl`; omitido se o agente não tem eventos.
- **Rodapé v2 (status bar)**:
  - REMOVE as dicas estáticas de mouse/atalhos do `status-right`.
  - ADICIONA `#S:#W` (sessão:window) e resumo de agentes via
    `#(sac status --mini)` — formato `<n>● <n>!` (claimed/escalados), omitindo
    contadores zerados.
  - MANTÉM: esquerda = modo (INPUT/KEY/COPY) + branch git; direita = título do
    pane + versão SAC + data/hora.
- **Novo `sac status --mini`**: saída de uma linha com os contadores de
  agentes claimed/escalados (para o `#(...)` do tmux; saída vazia se não houver
  sessão/store ativo — nunca quebra o status bar).

## Impact

- Código: `sac/commands.py` (`_render_sidebar`, `_comms_lines`, status bar no
  `cmd_up`), `sac/cli.py` (subcomando `status --mini`), `sac/store.py`
  (contagem de inbox, último evento por agente — leitura apenas).
- Specs: delta em `sessao-tmux` (sidebar v3 + status bar v2) e `cli`
  (`status --mini`).
- Compatibilidade: layout legado (sem `[windows]`) usa a mesma sidebar v3;
  nenhuma mudança de config exigida.
