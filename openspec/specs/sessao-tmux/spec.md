# Sessão Tmux

## Purpose
Gerenciamento da sessão tmux multi-agente: layout de janelas e panes, injeção de prompts, environment variables, socket dedicado e comandos tmux. O layout segue o padrão CCB: uma janela por agente com sidebar à esquerda (30 colunas) e harness à direita, mais uma janela dash com log e watcher.

## Requirements
### Requirement: Layout por janela com sidebar
Cada agente SHALL ter sua própria janela tmux com sidebar informativa e pane do harness.

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

### Requirement: Janela dash
O sistema SHALL criar uma janela de monitoramento com log e watcher.

#### Scenario: Criação da dash
- **WHEN** `sac up` é executado
- **THEN** uma janela `dash` é criada com sidebar + pane `sac log -f` + pane `sac notify`
- **AND** a aterrissagem inicial é na janela do leader, pane do harness

### Requirement: Environment variables
Cada harness SHALL receber a variável `SAC_AGENT=<nome>` para identificar seu papel.

#### Scenario: Injeção de SAC_AGENT
- **WHEN** o harness de um agente é iniciado
- **THEN** o comando executa com `env SAC_AGENT=<nome do agente>` prefixado
- **AND** comandos como `sac next` usam esta variável para determinar a inbox do agente

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
