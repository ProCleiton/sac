## ADDED Requirements

### Requirement: Persistência da largura da sidebar via hook client-resized
O sistema SHALL manter a largura de 30 colunas das sidebars mesmo quando clientes tmux com terminais de largura diferente se conectam.

#### Scenario: Hook registrado no boot
- **WHEN** `sac up` cria a sessão
- **THEN** um hook é registrado via `tmux set-hook -t <session> client-resized "..."` para re-aplicar resize das sidebars
- **AND** o hook executa `resize-pane -x 30` em todos os panes de sidebar de todas as janelas de agente

#### Scenario: Cliente attach redimensiona — sidebar restaurada
- **GIVEN** sessão ativa com sidebars de 30 cols
- **WHEN** um cliente attach com terminal de 80 cols e redimensiona para 120 cols (evento client-resized)
- **THEN** o hook dispara e re-aplica `resize-pane -x 30` nas sidebars
- **AND** a sidebar de cada janela de agente retorna a 30 cols

#### Scenario: Hook não afeta pane do harness
- **WHEN** o hook client-resized é executado
- **THEN** apenas panes identificados como sidebar (comando contendo "sac sidebar") são redimensionados
- **AND** o pane do harness de cada agente não é alterado

### Requirement: Identificação de pane sidebar por comando
O sistema SHALL conseguir localizar o pane da sidebar dentro de uma janela de agente para operações como kill e resize.

#### Scenario: find_sidebar_pane_id
- **WHEN** o sistema precisa do pane_id da sidebar de um agente
- **THEN** busca via `tmux list-panes -t <session>:<agent> -F "#{pane_id}|#{pane_start_command}"` por "sac sidebar"
- **AND** retorna o pane_id no formato `%N`

#### Scenario: find_sidebar_pane_id sem sessão
- **WHEN** não há sessão tmux ativa
- **THEN** retorna None

## MODIFIED Requirements

### Requirement: Layout por janela com sidebar (kill recriação)
O layout de janela SHALL suportar recriação do pane do harness após `sac kill` sem perder a estrutura sidebar + harness.

#### Scenario: Recriação de harness após kill
- **GIVEN** janela do agente com 2 panes: sidebar (esquerda) e harness (direita)
- **WHEN** o harness é morto via `sac kill`
- **THEN** o sistema localiza o pane_id da sidebar (que sobrevive)
- **AND** cria novo pane de harness via `tmux split-window -t <sidebar_id> -h` com o comando e env do agente
- **AND** aplica `resize-pane -x 30` na sidebar (pode ter sido resetada pelo kill)
- **AND** o novo pane recebe title com o nome do agente
- **AND** o prompt_file é re-injetado
