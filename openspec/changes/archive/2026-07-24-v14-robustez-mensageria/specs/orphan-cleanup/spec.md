## MODIFIED Requirements

### Requirement: Remoção de mensagens órfãs com dry-run
O sistema SHALL por padrão apenas listar os órfãos (dry-run) quando `--clean` é usado, exigindo `--yes` para executar a remoção destrutiva.

#### Scenario: Dry-run lista sem remover
- **GIVEN** `.sac/inbox/C/` contém mensagens (C não está em valid_agents)
- **WHEN** `clean_orphans(valid, dry_run=True)` é chamado
- **THEN** o diretório `.sac/inbox/C/` NÃO é removido
- **AND** o retorno inclui `inbox_files` e `claimed_files` com as contagens
- **AND** o evento `clean` é registrado com `dry_run=true`

#### Scenario: --yes executa remoção
- **GIVEN** `.sac/inbox/C/` contém mensagens
- **WHEN** `clean_orphans(valid, dry_run=False)` é chamado
- **THEN** `.sac/inbox/C/` é removido recursivamente
- **AND** `.sac/done/C/` é preservado

#### Scenario: Log do evento clean com dry_run
- **WHEN** `clean_orphans` é chamado (dry_run ou não)
- **THEN** o evento `clean` é registrado em `log.jsonl` com:
  - `agents_removed`: lista de nomes de agentes órfãos
  - `inbox_files` e `claimed_files`: contagens
  - `dry_run`: booleano indicando se foi simulação
