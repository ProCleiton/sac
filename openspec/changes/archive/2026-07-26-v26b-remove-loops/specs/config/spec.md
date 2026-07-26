## REMOVED Requirements

### Requirement: Declaração de loops
**Reason**: Loops declarados removidos (v26b) — decisão do usuário: delegação e
ciclos de revisão são disciplina do contrato do líder, não mecanismo do daemon.
**Migration**: remova a seção `[[loops]]` do config; expresse o ciclo no
contrato do líder (delegar com `sac send`, cobrar revisão, iterar).

## MODIFIED Requirements

### Requirement: Geração de sac.toml via template
O sistema SHALL gerar um arquivo de configuração válido a partir das respostas
do questionário `sac init`, escrito em `.sac/sac.toml` (o diretório `.sac/` é
criado se necessário).

#### Scenario: Template gerado com valores do questionário
- **GIVEN** valores fornecidos pelo usuário: nome="minha-esteira", leader="lead",
  workers=["dev-1","auditor"]
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML em `.sac/sac.toml` contém `[session] name = "minha-esteira"`
- **AND** `[[agents]]` para cada worker com os campos fornecidos
- **AND** o TOML é válido (parseável por `load_config`)

#### Scenario: Template com janelas agrupadas
- **GIVEN** usuário agrupou agentes em janelas no questionário
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML contém `[windows]` com as janelas declaradas

#### Scenario: Template sem loops
- **GIVEN** qualquer resposta do questionário
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML nunca contém seção `[[loops]]` (seção removida na v26b)

## ADDED Requirements

### Requirement: Config com seção loops é rejeitada
O sistema SHALL rejeitar com `ConfigError` claro um config que contenha a
seção `[[loops]]` (removida na v26b), orientando a remoção da seção e a
delegação via contrato do líder.

#### Scenario: config com loops falha com orientação
- **GIVEN** um `sac.toml` contendo `[[loops]]`
- **WHEN** `load_config` é executado
- **THEN** `ConfigError` informa que loops foram removidos e orienta remover a
  seção
