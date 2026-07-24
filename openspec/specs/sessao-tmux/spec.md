# Sessão Tmux

## Purpose
Gerenciamento da sessão tmux multi-agente: layout de janelas e panes, injeção de prompts, environment variables, socket dedicado, comandos tmux e inicialização do daemon de mensageria. O layout segue o padrão CCB: uma janela por agente com sidebar à esquerda (30 colunas) e harness à direita, mais uma janela dash com log e daemon.
## Requirements
### Requirement: Layout por janela com sidebar (kill recriação)
O layout de janela SHALL suportar recriação do pane do harness após `sac kill` sem perder a estrutura sidebar + harness.

#### Scenario: Criação de janela de agente
- **WHEN** `sac up` é executado
- **THEN** o primeiro agente (leader) é criado via `tmux new-session` com o comando sidebar
- **AND** os demais agentes são criados via `tmux new-window`
- **AND** cada janela contém: sidebar (30 cols, esquerda) + harness (divisão horizontal à direita)
- **AND** o harness recebe title com o nome do agente
- **AND** a sidebar executa `sh -c "while true; do clear; sac sidebar; sleep 5; done"` em loop infinito

#### Scenario: Redimensionamento da sidebar
- **WHEN** a janela é criada com split horizontal
- **THEN** o pane da sidebar é redimensionado para 30 colunas via `tmux resize-pane -x 30`

#### Scenario: Recriação de harness após kill
- **GIVEN** janela do agente com 2 panes: sidebar (esquerda) e harness (direita)
- **WHEN** o harness é morto via `sac kill`
- **THEN** o sistema localiza o pane_id da sidebar (que sobrevive)
- **AND** cria novo pane de harness via `tmux split-window -t <sidebar_id> -h` com o comando e env do agente
- **AND** aplica `resize-pane -x 30` na sidebar (pode ter sido resetada pelo kill)
- **AND** o novo pane recebe title com o nome do agente
- **AND** o prompt_file é re-injetado

### Requirement: Janela dash
O sistema SHALL criar uma janela de monitoramento com log e daemon.

#### Scenario: Criação da dash
- **WHEN** `sac up` é executado
- **THEN** uma janela `dash` é criada, dividida em 3 panes: sidebar (esquerda), `sac log -f` (centro) e `sac daemon` (direita)
- **AND** a aterrissagem inicial é na janela do leader, pane do harness

### Requirement: Daemon lifecycle na dash
O daemon SHALL ser iniciado automaticamente na janela dash e gerenciado pelo ciclo de vida da sessão.

#### Scenario: Daemon inicia com a sessão
- **WHEN** `sac up` cria a janela dash
- **THEN** o comando DASH_NOTIFY_CMD (`["sac", "daemon"]`) é executado em um dos panes
- **AND** o daemon escreve `.sac/daemon.pid` ao iniciar

#### Scenario: Daemon encerra com a sessão
- **WHEN** `sac down` encerra a sessão tmux
- **THEN** o daemon recebe SIGHUP via tmux e encerra, removendo `.sac/daemon.pid`

### Requirement: Environment variables
Cada harness SHALL receber a variável `SAC_AGENT=<nome>` para identificar seu papel.

#### Scenario: Injeção de SAC_AGENT
- **WHEN** o harness de um agente é iniciado
- **THEN** o comando executa com `env SAC_AGENT=<nome do agente>` prefixado
- **AND** comandos como `sac done` usam esta variável para determinar o agente corrente

### Requirement: Socket dedicado
O tmux SHALL suportar socket Unix dedicado para isolamento e acesso remoto.

#### Scenario: Socket configurado
- **GIVEN** `sac.toml` com `socket = "~/.sac/tmux.sock"`
- **WHEN** `sac up` é executado
- **THEN** todos os comandos tmux são prefixados com `-S ~/.sac/tmux.sock`
- **AND** pode ser acessado via SSH/Tailscale

#### Scenario: Socket não configurado
- **GIVEN** `sac.toml` sem `socket`
- **WHEN** `sac up` é executado
- **THEN** o tmux usa o socket default

### Requirement: Identificação de panes por comando
O sistema SHALL localizar panes pelo comando de inicialização que contém `SAC_AGENT=<nome>`.

#### Scenario: find_pane_id
- **WHEN** um comando precisa cutucar o pane de um agente
- **THEN** o sistema busca via `tmux list-panes -s -F pane_id|pane_start_command` por `SAC_AGENT=<nome>`
- **AND** retorna o pane_id no formato `%N` (raw, imune a base-index)

### Requirement: Injeção de prompts via paste
Prompts de contrato SHALL ser injetados nos harnesses via tmux paste buffer + Enter.

#### Scenario: Injeção automática no boot
- **WHEN** `sac up` é executado e o boot_wait expira
- **THEN** para cada agente com `prompt_file` configurado: o conteúdo do arquivo é carregado via `tmux load-buffer` e colado via `tmux paste-buffer -t <target>`
- **AND** após 0.5s, um Enter é enviado via `tmux send-keys -t <target> Enter`

#### Scenario: Injeção manual
- **WHEN** `sac inject <agente>` é executado
- **THEN** o mesmo processo de paste + Enter é aplicado apenas ao agente especificado

### Requirement: Envio de teclas com segurança
Comandos de texto enviados aos panes SHALL ser literais (sem interpretação de caracteres especiais).

#### Scenario: send-keys literal
- **WHEN** texto é enviado a um pane
- **THEN** `tmux send-keys -t <target> -l -- <text>` é usado (flag `-l` = literal)
- **AND** um Enter separado é enviado 0.5s depois

### Requirement: Aterrissagem no leader
Após a criação da sessão, o foco SHALL estar no leader.

#### Scenario: Select inicial
- **WHEN** `sac up` conclui a criação
- **THEN** `tmux select-window -t <session>:leader` e `tmux select-pane -t <harness_pane_id>` são executados

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

