## MODIFIED Requirements

### Requirement: Geração de sac.toml via template
O sistema SHALL gerar um arquivo de configuração válido a partir das respostas
do questionário `sac init`, escrito em `.sac/sac.toml` (o diretório `.sac/` é
criado se necessário).

#### Scenario: Template gerado com valores do questionário
- **GIVEN** valores fornecidos pelo usuário: nome="minha-esteira", leader="lead",
  workers=["dev-1","auditor"], loop="dev-review"
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML em `.sac/sac.toml` contém `[session] name = "minha-esteira"`
- **AND** `[[agents]]` para cada worker com os campos fornecidos
- **AND** `[[loops]]` com o loop declarado
- **AND** o TOML é válido (parseável por `load_config`)

#### Scenario: Template com janelas agrupadas
- **GIVEN** usuário agrupou agentes em janelas no questionário
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML contém `[windows]` com as janelas declaradas

#### Scenario: Template sem loops
- **GIVEN** usuário não declara loops
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML não contém seção `[[loops]]`
