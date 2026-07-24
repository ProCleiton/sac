## MODIFIED Requirements

### Requirement: boot_wait por agente
Cada agente declarado em `[[agents]]` SHALL poder sobrescrever o `boot_wait` global com um valor específico via campo `boot_wait`. O default global `[session].boot_wait` passa para 8 segundos.

#### Scenario: Agente com boot_wait específico
- **GIVEN** `sac.toml` com `[session] boot_wait = 8`
- **AND** `[[agents]]` com `name = "dev-1"`, `boot_wait = 12`
- **WHEN** o config é carregado
- **THEN** `AgentConfig.boot_wait` de dev-1 é 12
- **AND** agentes sem `boot_wait` recebem o global (8)

#### Scenario: Default global alterado para 8
- **GIVEN** `sac.toml` sem `[session] boot_wait`
- **WHEN** o config é carregado
- **THEN** `Config.boot_wait` é 8 (não mais 3)

#### Scenario: boot_wait zero (sem wait)
- **GIVEN** `[[agents]]` com `boot_wait = 0`
- **WHEN** o config é carregado
- **THEN** `AgentConfig.boot_wait` é 0
- **AND** `cmd_up` não espera antes de injetar o prompt desse agente

#### Scenario: boot_wait string inválida → ConfigError
- **GIVEN** `[[agents]]` com `boot_wait = "oito"`
- **WHEN** o config é carregado
- **THEN** o sistema rejeita com `ConfigError`

#### Scenario: boot_wait negativo → ConfigError
- **GIVEN** `[[agents]]` com `boot_wait = -1`
- **WHEN** o config é carregado
- **THEN** o sistema rejeita com `ConfigError`
