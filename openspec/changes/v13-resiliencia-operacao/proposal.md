## Why

O SAC v1.2 (daemon coordenador) provou o conceito em PR #1, mas expôs fragilidades
operacionais: (1) o loop `sac notify` morre silenciosamente em qualquer exceção —
sem rastro; (2) harness travado só se recupera com `sac down` + `sac up`, perdendo
estado; (3) attach de clientes com terminais de largura diferente achata a sidebar
de 30 cols; (4) não há limpeza de inbox de agentes removidos do `sac.toml`. A v1.3
endereça esses 4 pontos e resolve o tratamento de untracked files do repo.

## What Changes

- **Notify resiliente**: `cmd_notify` e `cmd_log -f` envelopam o sweep/loop em
  try/except com `store.log("loop_error")` (padrão já estabelecido no daemon).
- **`sac kill <agente>`**: novo comando que localiza o pane do harness, mata o
  processo, recria o pane no mesmo lugar (split a partir da sidebar), re-injeta
  o prompt_file e, se houver claimed pendente, alerta o agente.
- **Sidebar 30 cols persistente**: `set-hook client-resized` na sessão tmux
  re-aplica `resize-pane -x 30` nas sidebars de todas as janelas de agente.
- **Limpeza de inbox órfã**: flag `--clean` em `sac status` (ou comando separado)
  remove mensagens de agentes não declarados no `sac.toml` e inbox do usuário órfã.
- **Chore de repo**: `.opencode/` adicionado ao `.gitignore`; `AGENTS.md` —
  decidir se commita (não existe hoje) — se vazio/irrelevante, apenas garantir
  que não vaze para o repo.

## Capabilities

### New Capabilities
- `kill-agent`: reinicialização de harness travado via `sac kill <agente>`
- `orphan-cleanup`: limpeza de mensagens órfãs de agentes removidos da config

### Modified Capabilities
- `cli`: adiciona comando `kill` (nova capability kill-agent); adiciona `--clean`
  em `status` (nova capability orphan-cleanup); comportamento do `notify` e `log`
  muda para resiliente (try/except)
- `sessao-tmux`: ganha hook `client-resized` para persistir largura da sidebar;
  ganha cenário de recriação de pane no `kill`
- `core-mensageria`: ganha evento de log `loop_error` (notify/log); ganha
  capability de limpeza de mensagens órfãs

## Impact

**Código**: `sac/commands.py` (cmd_notify, cmd_log, cmd_kill, cmd_status_clean),
`sac/cli.py` (parser kill + flag --clean), `sac/tmux.py` (kill_pane, set-hook),
`sac/store.py` (método `clean_orphans()`), `sac/config.py` (nada — usa config
existente). Testes novos em `tests/test_commands.py` e `tests/test_store.py`.

**Dependências**: nenhuma nova — stdlib + tmux apenas.

**Risco**: baixo. `kill` só age no pane do harness (não na sidebar); hook
client-resized é evento tmux padrão; limpeza é operação de filesystem (remover
arquivos `.msg`).
