## ADDED Requirements

### Requirement: Sidebar v3 — árvore com conectores e modelo
A sidebar SHALL renderizar os agentes sob cada window com conectores de árvore
(`├─` para todos exceto o último, `└─` para o último) e SHALL exibir o modelo
do agente extraído de `--model <valor>` nos seus `args` (sem o prefixo de
alias, ex.: `esteira/k3` → `k3`) ao lado do comando — ex.: `kimi/k3`. Agente
sem `--model` exibe apenas o comando.

#### Scenario: Árvore com 2 agentes numa window
- **GIVEN** window `trabalho` com agentes `dev-1` (opencode) e `auditor`
  (kimi, `--model esteira/k3`)
- **WHEN** a sidebar é renderizada
- **THEN** `dev-1` aparece com prefixo `├─` e `auditor` com `└─`
- **AND** `auditor` exibe `kimi/k3` e `dev-1` exibe `opencode`

#### Scenario: Agente único na window
- **GIVEN** window `main` com apenas `leader`
- **WHEN** a sidebar é renderizada
- **THEN** `leader` aparece com prefixo `└─`

### Requirement: Sidebar v3 — badge de inbox e tempo ocioso
A sidebar SHALL exibir `(N)` ao lado do agente quando houver N > 0 mensagens
pendentes em `inbox/<agente>/`, e SHALL exibir `· <idade>` (minutos `5m`,
horas `1h`, dias `2d`) desde o último evento daquele agente no `log.jsonl`.
Agente sem eventos no log não exibe idade.

#### Scenario: Agente com inbox pendente e evento recente
- **GIVEN** `dev-1` com 2 mensagens na inbox e último evento há 5 minutos
- **WHEN** a sidebar é renderizada
- **THEN** a linha de `dev-1` contém `(2)` e `· 5m`

#### Scenario: Agente sem eventos
- **GIVEN** agente sem nenhum evento no `log.jsonl`
- **WHEN** a sidebar é renderizada
- **THEN** sua linha não contém marcador de idade

### Requirement: Status bar v2 — sem dicas estáticas, com sessão e resumo
O `status-right` SHALL remover as dicas estáticas de mouse/atalhos e SHALL
incluir `#S:#W` (sessão:window) e o resumo de agentes via
`#(sac status --mini)`. `status-left` (modo + branch), título do pane, versão
e data/hora são preservados.

#### Scenario: Status bar após `sac up`
- **GIVEN** sessão SAC no ar
- **WHEN** o `sac up` termina
- **THEN** `status-right` não contém `MouseDrag` nem `S-C-v`
- **AND** contém `#S:#W` e `#(sac status --mini`

### Requirement: Identidade estável do agente via `@agent` pane option
O `sac up` SHALL gravar `@agent=<nome>` como pane option em todo pane de
harness (layout grid e legado), e a sidebar e o status bar SHALL usar
`@agent` — NÃO `pane_title` — para identificar agentes, pois harnesses
sobrescrevem o título do pane após o boot (ex.: kimi → "Kimi Code").

#### Scenario: Harness troca o título do pane
- **GIVEN** sessão no ar com agente `leader` rodando kimi
- **WHEN** o kimi muda o `pane_title` para "Kimi Code"
- **THEN** a sidebar continua exibindo `leader` na árvore
- **AND** o status bar exibe `leader` como agente focado
