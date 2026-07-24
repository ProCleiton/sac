# CLI

## Purpose
Interface de linha de comando `sac` com 14 comandos para gerenciamento de sessão multi-agente, mensageria (com suporte a daemon opcional), monitoramento e depuração. Entrypoint via `python -m sac` ou comando `sac` (instalação opcional via `pip install -e .`). Argumento global `--config <path>` para caminho do `sac.toml` (default: `sac.toml` no diretório corrente).
## Requirements
### Requirement: Gerenciamento de sessão tmux
O sistema SHALL expor comandos para criar, inspecionar e destruir a sessão tmux multi-agente.

#### Scenario: up — iniciar sessão
- **WHEN** `sac up` é executado com `sac.toml` válido
- **THEN** o sistema cria a sessão tmux, uma janela por agente com sidebar + harness, janela dash (com log + daemon), e aterrissa no leader
- **AND** é idempotente (rejeita se sessão já existe)
- **AND** agentes com `prompt_file` configurado recebem o prompt injetado após `boot_wait` segundos

#### Scenario: down — encerrar sessão
- **WHEN** `sac down` é executado
- **THEN** a sessão tmux é encerrada via `tmux kill-session`
- **AND** o diretório `.sac/` é preservado (incluindo daemon.pid se existente — o daemon recebe SIGHUP via tmux)

#### Scenario: status — visão geral
- **WHEN** `sac status` é executado
- **THEN** o sistema exibe: sessão ativa/inativa, lista de agentes com role, janela existente (sim/não), inbox count, claimed count

#### Scenario: attach — conectar à sessão
- **WHEN** `sac attach` é executado
- **THEN** o sistema executa `tmux attach -t <session>` (com socket se configurado), substituindo o processo atual

### Requirement: Envio e consumo de mensagens
O sistema SHALL permitir comunicação assíncrona entre agentes via mensageria filesystem, com suporte a daemon de entrega direta.

#### Scenario: send — enviar mensagem (daemon ativo)
- **WHEN** `sac send <agente> "<corpo>"` é executado e o daemon está ativo (daemon.pid existe)
- **THEN** o sistema cria a mensagem em `inbox/<agente>/`, registra o evento no log, e NÃO cutuca o pane (o daemon fará a entrega direta)
- **AND** o sender é definido pela variável de ambiente `SAC_AGENT` ou "user" quando executado pelo usuário

#### Scenario: send — enviar mensagem (sem daemon)
- **WHEN** `sac send <agente> "<corpo>"` é executado e o daemon NÃO está ativo
- **THEN** o sistema cria a mensagem em `inbox/<agente>/`, registra o evento no log, e cutuca o pane com `"SAC: mensagem nova na inbox — rode \`sac next\`"`
- **AND** se o pane do agente não existe, exibe aviso no stderr (mensagem ainda está na inbox)

#### Scenario: next — consumir mensagem
- **WHEN** `sac next` é executado dentro do ambiente do agente (SAC_AGENT definido)
- **THEN** a mensagem mais antiga da inbox do agente é movida para claimed e exibida
- **AND** retorna 2 se `SAC_AGENT` não está definido

#### Scenario: done — concluir mensagem
- **WHEN** `sac done <id> "<resumo>"` é executado
- **THEN** a mensagem é movida de claimed para done com o resumo informado

#### Scenario: recv — ler resposta
- **WHEN** `sac recv <agente>` é executado
- **THEN** o sistema captura o pane do agente e busca a sentinela `SAC_DONE`
- **AND** se encontrada: exibe o texto completo (sem sentinela) e retorna 0
- **AND** se não encontrada: exibe "ainda processando" + últimos 500 caracteres e retorna 1
- **AND** o parâmetro `--lines N` permite controlar quantas linhas capturar (default 200)

### Requirement: Daemon de mensageria
O sistema SHALL expor um comando `daemon` que implementa o polling e entrega direta de mensagens.

#### Scenario: daemon — iniciar mensageria contínua
- **WHEN** `sac daemon` é executado
- **THEN** o sistema inicia o loop Daemon: a cada 1s varre inbox/claimed de todos agentes, entrega mensagens novas diretamente no pane, e re-cutuca mensagens claimed stale
- **AND** escreve `.sac/daemon.pid` com o PID do processo
- **AND** encerra limpo com SIGTERM/SIGINT, removendo o PID file

### Requirement: Resiliência em loops — try/except em cmd_notify
O sistema SHALL oferecer compatibilidade com o modelo notify original para operação sem daemon, com captura de exceções no loop de sweep para evitar morte silenciosa.

#### Scenario: notify — watcher contínuo (legado)
- **WHEN** `sac notify` é executado sem `--once`
- **THEN** o sistema entra em loop: a cada `notify_interval` segundos varre inbox/claimed
- **AND** mensagens mais velhas que `poke_stale_after` segundos provocam re-cutucada do agente com texto genérico
- **AND** o loop termina com Ctrl-C

#### Scenario: notify --once — varredura única
- **WHEN** `sac notify --once` é executado
- **THEN** o sistema executa uma única varredura de stale detection e sai

#### Scenario: Notify com try/except (já coberto em core-mensageria)
- **WHEN** `sac notify` roda e `notify_sweep` lança exceção
- **THEN** a exceção é capturada e registrada via `store.log("loop_error")`
- **AND** o loop continua

### Requirement: Resiliência em cmd_log -f
O sistema SHALL expor o log de eventos para acompanhamento em tempo real, com captura de exceções de leitura para evitar morte do pane.

#### Scenario: log — exibir log
- **WHEN** `sac log` é executado
- **THEN** o conteúdo de `.sac/log.jsonl` é exibido
- **AND** `sac log -f` segue o arquivo em tempo real (tail -f)

#### Scenario: Log -f com erro de leitura
- **WHEN** `sac log -f` encontra erro de I/O no arquivo de log
- **THEN** a exceção é capturada e registrada
- **AND** o loop `while True` continua tentando

### Requirement: Injeção de prompt
O sistema SHALL permitir re-injetar o prompt de contrato em agentes específicos.

#### Scenario: inject — re-injetar prompt
- **WHEN** `sac inject <agente>` é executado
- **THEN** o `prompt_file` do agente (se configurado) é re-injetado no pane via paste + Enter

### Requirement: Flag --clean em status
O sistema SHALL aceitar `sac status --clean` para gatilhar limpeza de mensagens órfãs.

#### Scenario: status --clean
- **WHEN** `sac status --clean` é executado
- **THEN** o sistema executa a limpeza de órfãos (ver core-mensageria)
- **AND** exibe o resultado da limpeza junto com o status normal

#### Scenario: status sem --clean
- **WHEN** `sac status` é executado sem `--clean`
- **THEN** o sistema exibe o status normal sem efetuar limpeza (comportamento inalterado)

### Requirement: Sidebar informativa
O sistema SHALL exibir um painel lateral com o estado atual dos agentes.

#### Scenario: sidebar — painel de estado
- **WHEN** `sac sidebar` é executado
- **THEN** o sistema renderiza: agentes com marcadores de estado (idle, inbox, working), atalhos C-b <N>, e loops declarados
- **AND** é usado internamente nos panes de sidebar de cada janela (loop `clear; sac sidebar; sleep 5`)

### Requirement: Execução de loops declarados
O sistema SHALL permitir iniciar um ciclo de trabalho pré-declarado no `sac.toml`.

#### Scenario: run — iniciar loop
- **WHEN** `sac run <loop> "<tarefa>"` é executado
- **THEN** uma mensagem com prefixo `[loop <nome>]` é enviada ao primeiro agente da sequência do loop
- **AND** o fluxo subsequente é guiado pelos prompts de contrato (não enforced pelo SAC)

### Requirement: Comando kill para reinicialização de harness
O sistema SHALL expor o comando `sac kill <agente>` para reiniciar o harness de um agente travado, preservando a estrutura da janela e as mensagens pending/claimed.

#### Scenario: Kill recria harness no mesmo lugar
- **GIVEN** uma janela com sidebar (30 cols) + pane do harness para o agente "dev-1"
- **AND** o harness está travado (não responde a input)
- **WHEN** `sac kill dev-1` é executado
- **THEN** o processo do harness é terminado via `tmux kill-pane -t <pane_id>`
- **AND** um novo pane é criado no mesmo lugar via `tmux split-window -t <sidebar_pane> -h` com o comando do agente e `env SAC_AGENT=dev-1`
- **AND** o prompt_file do agente é re-injetado (mesmo fluxo de `sac inject`)
- **AND** se há mensagens claimed pendentes, o agente recebe alerta: `"SAC: tarefa <id> pendente — rode \`sac done <id>\`"`
- **AND** o evento `kill` é registrado em `log.jsonl` com o agente e id das mensagens claimed repassadas

#### Scenario: Kill de agente inexistente
- **WHEN** `sac kill <agente>` é executado para um nome não declarado no `sac.toml`
- **THEN** o sistema retorna erro e exit code 1

#### Scenario: Kill sem sessão ativa
- **WHEN** `sac kill <agente>` é executado sem sessão tmux ativa
- **THEN** o sistema retorna erro informando que não há sessão

#### Scenario: Kill sem pane do agente
- **WHEN** `sac kill <agente>` é executado mas o pane do harness não é encontrado (ex.: janela sem harness)
- **THEN** o sistema retorna erro informando que o pane não existe

