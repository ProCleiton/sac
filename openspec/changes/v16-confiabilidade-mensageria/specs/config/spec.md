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
