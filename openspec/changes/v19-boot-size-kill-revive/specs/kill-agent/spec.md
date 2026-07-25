# Delta: kill-agent

## MODIFIED Requirements

### Requirement: Reinicialização de harness por pane kill
O sistema SHALL permitir reiniciar o harness de um agente específico matando e recriando seu pane tmux, sem afetar os demais agentes ou a sessão. Se o pane do harness não existir (ex.: processo morreu e o pane fechou), o sistema SHALL recriar o harness na janela correta em vez de abortar (ver "Revive de agente com pane morto").

#### Scenario: Identificação do pane do harness
- **WHEN** `sac kill <agente>` é executado
- **THEN** o sistema localiza o pane do harness via `tmux.list-panes` filtrando por `SAC_AGENT=<agente>` no `pane_start_command`
- **AND** se o pane não existe, segue o caminho de revive (recriação sem kill prévio)

#### Scenario: Kill do processo do harness
- **WHEN** o pane do harness é localizado
- **THEN** o sistema executa `tmux kill-pane -t <pane_id>` para terminar o processo
- **AND** aguarda confirmação de que o pane foi destruído

#### Scenario: Recriação do harness com mesmo ambiente
- **WHEN** o pane do harness foi destruído
- **THEN** o sistema localiza o pane da sidebar na mesma janela (via `pane_start_command` contendo "sac sidebar")
- **AND** cria novo harness via `tmux split-window -t <sidebar_pane_id> -h` com `env SAC_AGENT=<agente> <command> [args]`
- **AND** o title do novo pane é definido como o nome do agente
- **AND** a sidebar é redimensionada para 30 cols

#### Scenario: Re-injeção de prompt após kill
- **WHEN** o novo pane do harness é criado
- **AND** o agente tem `prompt_file` configurado
- **THEN** o conteúdo do prompt_file é injetado no novo pane

#### Scenario: Alerta de claimed pendente após kill
- **GIVEN** o agente tinha mensagens em `claimed/` antes do kill
- **WHEN** o harness é recriado
- **THEN** o sistema injeta `"SAC: tarefa <id> pendente — rode \`sac done <id>\`"` no novo pane para cada mensagem claimed
- **AND** o evento `kill` é registrado em `log.jsonl` com o nome do agente e ids das mensagens repassadas

#### Scenario: Nenhuma claimed — sem alerta
- **GIVEN** o agente não tinha mensagens claimed
- **WHEN** o harness é recriado
- **THEN** nenhum alerta de claimed é enviado
- **AND** o evento `kill` é registrado sem campo de ids claimed

### Requirement: Validação de pré-condições do kill
O sistema SHALL validar que o agente existe no config e a sessão está ativa antes de executar o kill. Pane inexistente NÃO é erro — aciona o revive.

#### Scenario: Agente inexistente
- **WHEN** `sac kill <agente>` com nome não declarado no sac.toml
- **THEN** retorna erro ConfigError e exit 1

#### Scenario: Sessão inativa
- **WHEN** `sac kill <agente>` sem sessão tmux ativa
- **THEN** retorna erro "sessão não ativa" e exit 1

#### Scenario: Pane não encontrado — revive
- **GIVEN** agente válido e sessão ativa
- **WHEN** o pane do harness não é encontrado (ex.: processo do harness morreu e o pane fechou)
- **THEN** o sistema executa o revive (recriação do harness na janela do agente) em vez de retornar erro

## ADDED Requirements

### Requirement: Revive de agente com pane morto
O sistema SHALL recriar o harness de um agente cujo pane não existe mais, localizando a janela-alvo pela config (layout legado: janela com o nome do agente; layout grid: janela cuja gramática `[windows]` contém o agente) e criando o pane a partir da sidebar dessa janela.

#### Scenario: Revive no layout legado
- **GIVEN** sessão sem `[windows]` e pane do harness do agente inexistente
- **WHEN** `sac kill <agente>` é executado
- **THEN** o sistema localiza a janela com o nome do agente e a sidebar nela
- **AND** cria o harness via `tmux split-window -t <sidebar_pane_id> -h` com `env SAC_AGENT=<agente> <command> [args]`
- **AND** define `@agent` e o título do pane como o nome do agente
- **AND** aguarda boot_wait, injeta o prompt_file e alerta claimeds pendentes como no kill normal

#### Scenario: Revive no layout grid
- **GIVEN** sessão com `[windows]` e pane do harness do agente inexistente
- **WHEN** `sac kill <agente>` é executado
- **THEN** o sistema resolve a janela-alvo pela gramática `[windows]` (janela que contém o agente)
- **AND** cria o harness a partir da sidebar dessa janela, com os mesmos passos do revive legado

#### Scenario: Janela ou sidebar inexistente — erro
- **GIVEN** pane do harness inexistente
- **WHEN** a janela-alvo ou a sidebar dela também não existe
- **THEN** retorna erro indicando que não foi possível localizar a janela/sidebar do agente e exit 1
