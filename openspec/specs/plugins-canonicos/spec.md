# plugins-canonicos Specification

## Purpose
TBD - created by archiving change v27-plugins-canonicos. Update Purpose after archive.
## Requirements
### Requirement: Manifest de plugins canônicos
O sistema SHALL embutir um manifest de plugins canônicos (dados, em módulo
próprio): superpowers (tipo skills, repo obra/superpowers), RTK (tipo
cli-binary, repo rtk-ai/rtk) e openspec (tipo cli-npm, repo
Fission-AI/OpenSpec), cada um com ref pinada. Os plugins vivem em
`$SAC_HOME/plugins/<nome>/` (clones) e seus binários em `$SAC_HOME/bin/`
(`SAC_HOME` default `~/.sac`). O SAC NÃO lê instalações de harness
(`~/.kimi-code/plugins`, `~/.claude`, etc.) — dentro da esteira vale apenas a
cópia gerenciada pelo SAC.

#### Scenario: manifest contém os 3 canônicos com ref pinada
- **WHEN** o manifest é carregado
- **THEN** superpowers, rtk e openspec estão presentes com tipo, repo e ref

#### Scenario: SAC_HOME sobrescrevível
- **WHEN** a env `SAC_HOME` está definida
- **THEN** clones e bins usam esse diretório em vez de `~/.sac`

### Requirement: Comando sac plugins
O sistema SHALL expor `sac plugins` com subcomandos `install`, `update`,
`status` e `uninstall`. `install` clona cada plugin na ref pinada e
materializa binários (rtk: asset do release em `$SAC_HOME/bin/`; openspec:
`npm install --prefix` + shim), é idempotente e falha com erro claro sem
rede. `update` faz fetch+checkout da ref pinada; `--check` compara pin ×
upstream sem alterar nada. `status` reporta por plugin: instalado, ref atual,
bin presente. `uninstall` remove clones e bins com confirmação.

#### Scenario: install clona na ref pinada e materializa bins
- **GIVEN** `$SAC_HOME` vazio
- **WHEN** `sac plugins install` é executado
- **THEN** cada repo é clonado e a ref pinada é checked out
- **AND** `$SAC_HOME/bin/rtk` e `$SAC_HOME/bin/openspec` existem

#### Scenario: install é idempotente
- **GIVEN** plugins já instalados na ref pinada
- **WHEN** `sac plugins install` é executado novamente
- **THEN** nada é reclonado e o resultado é sucesso

#### Scenario: update --check não altera nada
- **WHEN** `sac plugins update --check` é executado
- **THEN** pin × upstream são exibidos e nenhum arquivo muda

#### Scenario: uninstall exige confirmação
- **WHEN** `sac plugins uninstall` é executado
- **THEN** os alvos são listados e só removidos após confirmação

### Requirement: Injeção dos plugins nos agentes
No `sac up`, o sistema SHALL colocar `$SAC_HOME/bin` no início do PATH de todo
pane de agente (binários do SAC têm precedência sobre qualquer instalação
externa) e SHALL aplicar adapters por harness (tabela data-driven): `kimi`
recebe `--skills-dir $SAC_HOME/plugins/superpowers/skills` quando o
superpowers estiver instalado (substitui a auto-descoberta); `opencode` e
`mimo` recebem `--pure`; `claude` recebe `--bare --plugin-dir
$SAC_HOME/plugins/superpowers`; `copilot` recebe a env `COPILOT_SKILLS_DIRS`
com o skills dir do SAC; `codex` recebe `-c skills.config=[...]` apontando o
skills dir do SAC. Harness sem adapter recebe apenas o ponteiro no contrato.

#### Scenario: PATH do pane prioriza binários do SAC
- **WHEN** um pane de agente é criado no `sac up`
- **THEN** seu PATH começa com `$SAC_HOME/bin`

#### Scenario: kimi recebe --skills-dir do SAC
- **GIVEN** superpowers instalado e agente com command `kimi`
- **WHEN** o agente é iniciado
- **THEN** seus args incluem `--skills-dir $SAC_HOME/plugins/superpowers/skills`

#### Scenario: sem superpowers instalado, nenhum arg extra
- **GIVEN** superpowers NÃO instalado
- **WHEN** o agente kimi é iniciado
- **THEN** seus args não incluem `--skills-dir`

#### Scenario: opencode recebe --pure
- **GIVEN** agente com command `opencode` ou `mimo`
- **WHEN** o agente é iniciado no `sac up`
- **THEN** seus args incluem `--pure` (sem plugins externos)

#### Scenario: claude recebe --bare e --plugin-dir
- **GIVEN** superpowers instalado e agente com command `claude`
- **WHEN** o agente é iniciado
- **THEN** seus args incluem `--bare` e `--plugin-dir $SAC_HOME/plugins/superpowers`

#### Scenario: copilot recebe COPILOT_SKILLS_DIRS
- **GIVEN** superpowers instalado e agente com command `copilot`
- **WHEN** o pane é criado
- **THEN** seu env inclui `COPILOT_SKILLS_DIRS=$SAC_HOME/plugins/superpowers/skills`

#### Scenario: harness desconhecido usa só o contrato
- **GIVEN** agente com command fora da tabela de adapters
- **WHEN** o agente é iniciado
- **THEN** não recebe args/env de skills — apenas o PATH e o ponteiro no contrato

### Requirement: Disciplina de plugins canônicos nos contratos
Os contratos canônicos SHALL incluir: RTK obrigatório em comandos verbosos
(`rtk err`, `rtk test`, `rtk git`, `rtk docker`; exceção: saída completa
necessária) — líder e aux; ponteiro para as skills do superpowers em
`$SAC_HOME/plugins/superpowers/skills/` (ler a skill aplicável à tarefa) —
líder e aux; openspec para specs/changes — líder e contrato de documentação;
e a disciplina de delegação do líder SHALL instruir a ferramenta canônica por
tarefa (RTK sempre; openspec quando envolver spec/change; skill superpowers
aplicável).

#### Scenario: todos os contratos têm RTK e ponteiro de skills
- **WHEN** os prompts são gerados pelo init
- **THEN** líder e aux contêm a regra do RTK e o caminho das skills do SAC

#### Scenario: líder instrui ferramenta canônica ao delegar
- **WHEN** o contrato do líder é gerado
- **THEN** ele contém a regra de indicar a ferramenta canônica na delegação
- **AND** contém openspec para specs/changes

#### Scenario: documentação recebe openspec
- **WHEN** o contrato de documentação é gerado
- **THEN** ele menciona openspec para specs/changes

### Requirement: Doctor verifica plugins canônicos
O `sac doctor` SHALL verificar cada plugin canônico (clone na ref pinada,
binário presente) como itens não essenciais: `[OK]` quando sincronizado,
`[WARN]` com orientação `sac plugins install` quando ausente ou
dessincronizado.

#### Scenario: plugins ausentes geram WARN
- **GIVEN** `$SAC_HOME` sem plugins
- **WHEN** `sac doctor` é executado
- **THEN** cada plugin ausente gera `[WARN]` com a correção
- **AND** exit code permanece 0

#### Scenario: plugins sincronizados geram OK
- **GIVEN** os 3 plugins instalados na ref pinada com bins presentes
- **WHEN** `sac doctor` é executado
- **THEN** cada plugin reporta `[OK]` com a ref

