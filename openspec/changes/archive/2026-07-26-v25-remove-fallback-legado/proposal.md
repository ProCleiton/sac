# Proposal — v25-remove-fallback-legado

## Por quê

A v24 introduziu o config oculto (`.sac/sac.toml`) com fallback para o legado
(`./sac.toml`) para não quebrar esteiras existentes. O usuário decidiu remover
o fallback: a esteira do workspace Github será desinstalada e recriada com o
wizard novo, e a ambiguidade de dois caminhos deixa de existir. Descoberta
passa a ser: `--config` > `$SAC_CONFIG` > `./.sac/sac.toml` — só.

## O que muda

- `resolve_config_path()` deixa de considerar `./sac.toml`.
- Workspace com apenas `sac.toml` na raiz → erro claro orientando a migração
  (`mkdir -p .sac && mv sac.toml .sac/`) ou `sac init`.
- `sac doctor`: WARN de ambiguidade vira "legado ignorado" (orienta mover ou
  apagar o `sac.toml` da raiz).
- `sac uninstall` continua removendo o `sac.toml` legado se existir (limpeza).
- README e guias do iniciante atualizados (cadeia sem fallback + nota de
  migração).

## Breaking change

Esteiras com `sac.toml` na raiz param de ser encontradas após o merge.
Migração manual: `mkdir -p .sac && mv sac.toml .sac/sac.toml` (o estado da
mensageria já vive em `.sac/`, nada mais muda). Workspace Github: o usuário
fará `sac uninstall` (com backup de `prompts/`) + `sac init` novo.

## Non-goals

- Migração automática (`sac migrate`) — o erro orienta o comando manual.
- Mudar o formato do config.

## Specs afetadas

- `cli` (REMOVED: Resolução de config via env da sessão; ADDED: Descoberta de
  config; MODIFIED: Comando doctor)
