# Config

## Purpose
Arquivo de configuração `sac.toml` no formato TOML usando `tomllib` da stdlib Python (3.11+). Define a sessão tmux, os agentes participantes e os loops de trabalho declarados. As mesmas configurações de temporização (`notify_interval`, `poke_stale_after`) são usadas pelo daemon de mensageria. Validações: nomes únicos, exatamente um leader, referências de loop válidas.
## Requirements
### Requirement: Configuração de sessão tmux
O sistema SHALL ler parâmetros da sessão tmux a partir de `[session]` no `sac.toml`.

#### Scenario: Seção session completa
- **GIVEN** um `sac.toml` com `[session]` contendo `name`, `notify_interval`, `poke_stale_after`, `boot_wait` e `socket`
- **WHEN** o arquivo é carregado
- **THEN** `session_name` é `"sac"`, `notify_interval` é 10, `poke_stale_after` é 10, `boot_wait` é 12, `socket` é `"~/.sac/tmux.sock"`

#### Scenario: Defaults aplicados
- **GIVEN** um `sac.toml` com `[session]` contendo apenas `name`
- **WHEN** o arquivo é carregado
- **THEN** os defaults são aplicados: `notify_interval=30`, `poke_stale_after=120`, `boot_wait=12`, `socket=None`

### Requirement: Declaração de agentes
O sistema SHALL aceitar múltiplos agentes declarados em `[[agents]]`, com papéis `leader` e `aux`, e suporte a `boot_wait` opcional por agente.

#### Scenario: Agente completo
- **GIVEN** `[[agents]]` com `name`, `command`, `args[]`, `role`, `prompt_file` e `boot_wait`
- **WHEN** o arquivo é carregado
- **THEN** o agente é configurado com todos os campos

#### Scenario: Agente sem prompt_file
- **GIVEN** `[[agents]]` sem `prompt_file`
- **WHEN** o arquivo é carregado
- **THEN** `prompt_file` é `None` e o agente não recebe injeção automática de prompt

#### Scenario: Agente sem boot_wait (usa global)
- **GIVEN** `[[agents]]` sem `boot_wait`
- **WHEN** o arquivo é carregado
- **THEN** o agente usa o valor global `[session].boot_wait` como default

#### Scenario: Nomes duplicados
- **GIVEN** `[[agents]]` com dois agentes de mesmo `name`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro de validação

#### Scenario: Role inválida
- **GIVEN** `[[agents]]` com `role` diferente de `"leader"` ou `"aux"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro de validação

### Requirement: Leader único
Exatamente um agente SHALL ter `role = "leader"`.

#### Scenario: Sem leader
- **GIVEN** `[[agents]]` sem nenhum agente com `role = "leader"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro

#### Scenario: Dois leaders
- **GIVEN** `[[agents]]` com dois agentes de `role = "leader"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro

### Requirement: Declaração de loops
O sistema SHALL aceitar loops de trabalho declarados em `[[loops]]`, com sequência de agentes e limite de iterações.

#### Scenario: Loop completo
- **GIVEN** `[[loops]]` com `name`, `sequence[]` e `max_iterations`
- **WHEN** o arquivo é carregado
- **THEN** `name` é o identificador, `sequence` é a lista ordenada de agentes, `max_iterations` é o limite máximo

#### Scenario: Loop sem max_iterations
- **GIVEN** `[[loops]]` sem `max_iterations`
- **WHEN** o arquivo é carregado
- **THEN** o default `max_iterations=3` é aplicado

#### Scenario: Agente desconhecido no loop
- **GIVEN** `[[loops]]` com `sequence` contendo um nome de agente que não existe em `[[agents]]`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro de validação

### Requirement: Acesso programático a agentes
O sistema SHALL expor métodos para lookup de agente por nome e acesso ao leader.

#### Scenario: Lookup por nome
- **WHEN** `config.agent("dev-1")` é chamado
- **THEN** retorna o `AgentConfig` correspondente ou lança erro se não existir

#### Scenario: Property leader
- **WHEN** `config.leader` é acessado
- **THEN** retorna o `AgentConfig` com `role = "leader"`

### Requirement: Geração de sac.toml via template
O sistema SHALL gerar um arquivo `sac.toml` válido a partir das respostas do
questionário `sac init`.

#### Scenario: Template gerado com valores do questionário
- **GIVEN** valores fornecidos pelo usuário: nome="minha-esteira", leader="lead",
  workers=["dev-1","auditor"], loop="dev-review"
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML contém `[session] name = "minha-esteira"`
- **AND** `[[agents]]` para cada worker com os campos fornecidos
- **AND** `[[loops]]` com o loop declarado
- **AND** o TOML é válido (parseável por `load_config`)

#### Scenario: Template sem loops
- **GIVEN** usuário não declara loops
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML não contém seção `[[loops]]`

