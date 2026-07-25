## MODIFIED Requirements

### Requirement: Seção session com root opcional
O sistema SHALL aceitar campo `root` opcional na seção `[session]` do `sac.toml`
para definir a raiz explícita do diretório `.sac/`.

#### Scenario: Session com root
- **GIVEN** `[session]` contém `root = "/home/dev/Github"`
- **WHEN** o arquivo é carregado
- **THEN** `session.root` é `"/home/dev/Github"`
- **AND** o Store usa `/home/dev/Github/.sac` como diretório de mensageria

#### Scenario: Session sem root
- **GIVEN** `[session]` sem campo `root`
- **WHEN** o arquivo é carregado
- **THEN** `session.root` é `None`
- **AND** o Store usa o comportamento atual (cwd)

#### Scenario: Validação — root precisa ser caminho absoluto
- **GIVEN** `[session]` com `root = "relativo/path"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro: "root deve ser caminho absoluto"

### Requirement: Seção session com poke_escalate_after opcional
O sistema SHALL aceitar campo `poke_escalate_after` opcional na seção
`[session]` do `sac.toml`, definindo quantos pokes sem `done` disparam o
escalonamento automático ao líder (default 3).

#### Scenario: Session com poke_escalate_after
- **GIVEN** `[session]` contém `poke_escalate_after = 5`
- **WHEN** o arquivo é carregado
- **THEN** `session.poke_escalate_after` é `5`

#### Scenario: Session sem poke_escalate_after
- **GIVEN** `[session]` sem o campo
- **WHEN** o arquivo é carregado
- **THEN** `session.poke_escalate_after` é `3` (default)

#### Scenario: Validação — valor mínimo 1
- **GIVEN** `[session]` com `poke_escalate_after = 0`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro: "poke_escalate_after deve ser >= 1"
