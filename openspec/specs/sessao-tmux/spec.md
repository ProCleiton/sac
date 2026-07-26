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
O sistema SHALL selecionar ao final do `sac up` a primeira window declarada
em `[windows]`; sem `[windows]`, mantém o select na window do leader.

#### Scenario: Select inicial
- **WHEN** `sac up` conclui a criação sem `[windows]`
- **THEN** `tmux select-window -t <session>:leader` e `tmux select-pane -t <harness_pane_id>` são executados

#### Scenario: Attach na entry window
- **GIVEN** `[windows]` com `main = "leader"` declarada primeiro
- **WHEN** `sac up` conclui
- **THEN** a window selecionada é `main` e o pane focado é o do leader

### Requirement: Persistência da largura da sidebar via hook client-resized
O sistema SHALL manter a largura da sidebar (15%, mínimo 28 colunas) em TODAS
as windows com sidebar quando o cliente redimensiona, em vez de assumir 1
window por agente.

#### Scenario: Hook registrado no boot
- **WHEN** `sac up` cria a sessão
- **THEN** um hook é registrado via `tmux set-hook -t <session> client-resized "..."` para re-aplicar resize das sidebars
- **AND** o hook executa `resize-pane` nos panes marcados `@pane_role=sidebar` de todas as windows

#### Scenario: Cliente attach redimensiona — sidebar restaurada
- **GIVEN** sessão ativa com sidebars na largura do plano
- **WHEN** um cliente attach com terminal de largura diferente (evento client-resized)
- **THEN** o hook dispara e re-aplica a largura da sidebar em cada window

#### Scenario: Hook não afeta pane do harness
- **WHEN** o hook client-resized é executado
- **THEN** apenas panes com `@pane_role=sidebar` são redimensionados
- **AND** o pane do harness de cada agente não é alterado

#### Scenario: Resize com layout em grid
- **GIVEN** sessão com `[windows]` (grid) no ar
- **WHEN** o terminal é redimensionado
- **THEN** o hook reaplica a largura da sidebar em cada window do plano

#### Scenario: Resize com layout legado
- **GIVEN** sessão sem `[windows]` no ar
- **WHEN** o terminal é redimensionado
- **THEN** o comportamento atual (sidebar 30 colunas por window de agente) é
  preservado

### Requirement: Identificação de pane sidebar por comando
O sistema SHALL conseguir localizar o pane da sidebar dentro de uma janela de agente para operações como kill e resize.

#### Scenario: find_sidebar_pane_id
- **WHEN** o sistema precisa do pane_id da sidebar de um agente
- **THEN** busca via `tmux list-panes -t <session>:<agent> -F "#{pane_id}|#{pane_start_command}"` por "sac sidebar"
- **AND** retorna o pane_id no formato `%N`

#### Scenario: find_sidebar_pane_id sem sessão
- **WHEN** não há sessão tmux ativa
- **THEN** retorna None

### Requirement: Progresso na criação de janelas (boot)
O sistema SHALL exibir progresso durante a criação da sessão tmux.

#### Scenario: Criação de janela com progresso
- **WHEN** `sac up` cria janelas e sidebars
- **THEN** imprime `[N/total] nome: criando janela...` antes de cada comando tmux

### Requirement: Progresso na criação da dash
A criação da dash SHALL exibir progresso.

#### Scenario: Criação da dash com progresso
- **WHEN** `sac up` cria a janela dash
- **THEN** imprime `[N/total] dash: criando janela...`

### Requirement: Fail-fast em comandos tmux críticos
O sistema SHALL abortar com erro claro se um comando tmux crítico falhar.

#### Scenario: Erro de socket aborta up
- **GIVEN** socket configurado com diretório inexistente (não criado automaticamente)
- **WHEN** `sac up` executa o primeiro comando tmux
- **THEN** a exceção `TmuxError` é levantada
- **AND** o cli.py captura e imprime mensagem com sugestão de correção
- **AND** o up retorna exit 1

#### Scenario: kill_pane falha — tolerante
- **GIVEN** pane inexistente
- **WHEN** `sac kill agent` chama `kill_pane`
- **THEN** o comando tmux falha silenciosamente (rc≠0 ignorado)
- **AND** o kill continua (tolerante)

#### Scenario: has_session falha — tolerante
- **WHEN** tmux não está instalado
- **THEN** `has_session()` retorna False (rc≠0 é falso, não exceção)
- **AND** não aborta o programa

### Requirement: Criação do diretório-pai do socket
O sistema SHALL criar o diretório do socket se não existir, antes do primeiro
comando tmux.

#### Scenario: mkdir antes do primeiro tmux
- **WHEN** `sac up` inicia
- **THEN** se `cfg.socket` está definido, `Path(socket).parent.mkdir(parents=True, exist_ok=True)` é executado
- **AND** a criação ocorre antes de `tmux new-session`

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

### Requirement: Envio de teclas com delay e Enter extra
O sistema SHALL, ao enviar teclas para panes tmux em contexto de mensageria
(daemon deliver, poke), usar delay de 0.2s entre o texto e o Enter, além de
incluir hint textual para destravar harness dormente.

#### Scenario: send-keys com delay para mensageria
- **WHEN** o daemon ou poke manual envia mensagem para um pane
- **THEN** o texto é injetado via `tmux send-keys -t <target> -l -- <text>` (literal)
- **AND** após 0.2s, um Enter é enviado via `tmux send-keys -t <target> Enter`
- **AND** o texto injetado contém hint `"SAC: mensagem — rode \`sac next\`"` ao final

### Requirement: Injeção de prompt com contrato de escalação
O sistema SHALL preceder todo prompt injetado (boot e `sac inject`) com o
contrato de escalação padrão, formatado com o nome do líder da configuração.

#### Scenario: Contrato precede o prompt_file
- **WHEN** `_inject_prompt` injeta o prompt de um agente
- **THEN** o contrato de escalação é injetado antes do conteúdo do prompt_file
- **AND** o nome do líder no contrato é o do agente com role `leader`

### Requirement: Sessão criada com tamanho explícito
O sistema SHALL criar a sessão tmux com tamanho explícito (`tmux new-session -d -x <width> -y <height>`), usando os valores de `[session] width`/`height` (default 220x50), para que harnesses bootem com geometria estável independente de cliente attachado. Sessão detached sem tamanho explícito nasce 80x24, o que mata harnesses sensíveis a panes estreitos (ex.: opencode crasha com SIGILL em panes de ~26 col).

#### Scenario: new-session recebe -x/-y
- **WHEN** `sac up` cria a sessão
- **THEN** o comando `tmux new-session -d` inclui `-x <width>` e `-y <height>` da config

#### Scenario: Grid calcula larguras sobre o tamanho configurado
- **GIVEN** layout `[windows]` com gramática lado a lado (`;`)
- **WHEN** a sessão é criada com 220x50
- **THEN** os panes de harness nascem com larguras proporcionais a 220 colunas (ex.: 3 colunas ≈ 70+ col cada)

#### Scenario: Sessão existente não é afetada
- **WHEN** `sac up` encontra sessão já ativa
- **THEN** retorna sem recriar nem redimensionar a sessão existente

### Requirement: Env de sessão exportada aos panes
O sistema SHALL exportar `SAC_ROOT` (raiz do store) e `SAC_CONFIG` (caminho absoluto do sac.toml da sessão) no ambiente de todo pane criado — harnesses (via `sac up` e `sac kill`), sidebars e panes do dashboard — para que comandos `sac` executados nos panes resolvam sempre a sessão correta, independente do cwd do processo.

#### Scenario: Pane de harness recebe env completa
- **WHEN** `sac up` ou `sac kill` cria o pane de um harness
- **THEN** o processo inicia com `SAC_AGENT=<agente>`, `SAC_ROOT=<raiz do store>` e `SAC_CONFIG=<caminho absoluto do config>`

#### Scenario: Panes de sidebar e dashboard recebem env de sessão
- **WHEN** `sac up` cria panes de sidebar ou dashboard (log, daemon)
- **THEN** os processos iniciam com `SAC_ROOT` e `SAC_CONFIG` (sem `SAC_AGENT`)

