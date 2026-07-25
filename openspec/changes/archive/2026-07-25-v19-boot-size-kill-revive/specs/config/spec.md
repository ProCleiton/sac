# Delta: config

## ADDED Requirements

### Requirement: Tamanho da sessão tmux no boot
O sistema SHALL permitir configurar o tamanho inicial da sessão tmux via `[session] width` e `[session] height` (inteiros positivos), com default de 220x50 quando ausentes.

#### Scenario: Defaults sem configuração
- **WHEN** o `sac.toml` não declara `width`/`height` em `[session]`
- **THEN** a config resultante usa width=220 e height=50

#### Scenario: Override explícito
- **WHEN** `[session]` declara `width = 180` e `height = 40`
- **THEN** a config resultante usa width=180 e height=40

#### Scenario: Valor inválido
- **WHEN** `width` ou `height` não é inteiro positivo
- **THEN** o sistema levanta ConfigError indicando a chave inválida

### Requirement: Init agnóstico de ambiente
O sistema SHALL gerar configuração e prompts sem referências a nenhum ambiente, harness configurado, alias de modelo ou caminho específico — o SAC é um gerenciador de harness agnóstico e toda escolha de modelo/comando é do usuário, via args do agente.

#### Scenario: Notas de harness sem modelo hardcoded
- **WHEN** `sac init` gera os prompts dos agentes
- **THEN** as notas de harness (kimi/opencode) descrevem o harness genericamente, sem indicar alias ou modelo específico

#### Scenario: Pergunta de modelo sem exemplo de ambiente
- **WHEN** o questionário pergunta o modelo de um agente
- **THEN** o exemplo exibido é genérico e a resposta vazia significa "não passar --model"
