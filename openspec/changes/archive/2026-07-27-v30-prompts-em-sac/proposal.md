# Proposal — v30-prompts-em-sac

## Por quê

Decisão do usuário (26/07): os contratos (`prompt_file`) são o último
artefato do SAC poluindo a raiz do workspace. Config foi para `.sac/sac.toml`
(v24), memória para `.sac/memory.db` (v26), plugins são SAC-owned (v27) —
falta os prompts. Tudo que é do SAC vive em `.sac/`.

## O que muda

- `sac init` gera os contratos em `.sac/prompts/<nome>.md` e grava
  `prompt_file = ".sac/prompts/<nome>.md"` no config (a resolução é relativa
  ao workspace root — transparente para `sac up` e para a injeção de memória).
- Checklist/banner/docs atualizados. `sac uninstall` continua removendo o
  `prompts/` legado da raiz (limpeza de migração), além de `.sac/`.

## Breaking change

Esteiras existentes têm `prompts/` na raiz. Migração: `mv prompts .sac/` +
ajustar `prompt_file` no config (ou `sac init` novo).

## Specs afetadas

- `cli` (MODIFIED: Comando init)
- `memoria` (MODIFIED: Injeção orçada no contrato do leader — caminho)
