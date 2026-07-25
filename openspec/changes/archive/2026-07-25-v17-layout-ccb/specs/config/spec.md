## ADDED Requirements

### Requirement: Seção [windows] opcional
O sistema SHALL aceitar uma seção `[windows]` no `sac.toml` onde cada chave é
o nome de uma window e o valor é um spec de layout (gramática `;`/`,`), e
SHALL validar a cobertura exata dos agentes declarados.

#### Scenario: Config com [windows] válido
- **GIVEN** 3 agentes (leader, dev-1, auditor) e
  `[windows]` com `main = "leader"` e `trabalho = "dev-1,auditor"`
- **WHEN** o arquivo é carregado
- **THEN** `cfg.windows` contém as duas entradas na ordem declarada

#### Scenario: Config sem [windows]
- **GIVEN** config sem a seção
- **WHEN** o arquivo é carregado
- **THEN** `cfg.windows` é vazio (layout legado)

#### Scenario: Agente desconhecido no spec
- **GIVEN** `[windows]` com `main = "leader;fantasma"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com ConfigError citando o agente desconhecido

#### Scenario: Agente duplicado nos specs
- **GIVEN** `[windows]` com `main = "leader"` e `x = "leader,dev-1"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com ConfigError (agente em mais de um pane)

#### Scenario: Agente ausente dos specs
- **GIVEN** 3 agentes e `[windows]` cobrindo apenas 2
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com ConfigError citando o agente ausente
