## ADDED Requirements

### Requirement: Detecção de mensagens órfãs
O sistema SHALL identificar diretórios em `.sac/inbox/` e `.sac/claimed/` que não correspondem a agentes declarados no `sac.toml`.

#### Scenario: Detecção de agente removido
- **GIVEN** `sac.toml` declara agentes ["leader", "dev-1"]
- **AND** `.sac/inbox/` contém diretórios: "leader", "dev-1", "auditor" (auditor foi removido)
- **WHEN** a detecção de órfãos é executada
- **THEN** "auditor" é identificado como órfão
- **AND** "leader" e "dev-1" não são listados como órfãos

#### Scenario: Inbox "user" identificada como órfã
- **GIVEN** `.sac/inbox/user/` contém mensagens
- **AND** "user" não é um agente declarado no sac.toml
- **WHEN** a detecção é executada
- **THEN** "user" é identificado como órfão

#### Scenario: Nenhum órfão — lista vazia
- **GIVEN** todos os diretórios em `.sac/inbox/` correspondem a agentes no sac.toml
- **WHEN** a detecção é executada
- **THEN** a lista de órfãos é vazia

### Requirement: Remoção de mensagens órfãs
O sistema SHALL remover mensagens de agentes órfãos (inbox e claimed), preservando o diretório done como histórico.

#### Scenario: Remoção de inbox e claimed órfãos
- **WHEN** `sac status --clean` identifica "auditor" como órfão
- **THEN** `.sac/inbox/auditor/` é removido recursivamente
- **AND** `.sac/claimed/auditor/` é removido recursivamente (se existir)
- **AND** `.sac/done/auditor/` é preservado

#### Scenario: Log do evento clean
- **WHEN** a limpeza remove diretórios órfãos
- **THEN** o evento `clean` é registrado em `log.jsonl` com:
  - `agents_removed`: lista de nomes de agentes órfãos
  - `inbox_files`: contagem total de arquivos .msg removidos de inbox
  - `claimed_files`: contagem total de arquivos .msg removidos de claimed

#### Scenario: Nada para limpar
- **GIVEN** não há diretórios órfãos
- **WHEN** `sac status --clean` é executado
- **THEN** o sistema informa "sem órfãos" na saída padrão
- **AND** nenhum diretório é removido
