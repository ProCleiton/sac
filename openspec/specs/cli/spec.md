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
O sistema SHALL permitir comunicação assíncrona entre agentes via mensageria filesystem, com suporte a daemon de entrega direta e auto-ack de respostas (reply_to).

#### Scenario: send — enviar mensagem (daemon ativo)
- **WHEN** `sac send <agente> "<corpo>"` é executado e o daemon está ativo (daemon.pid existe)
- **THEN** o sistema cria a mensagem em `inbox/<agente>/`, registra o evento no log, e NÃO cutuca o pane (o daemon fará a entrega direta)
- **AND** o sender é definido pela variável de ambiente `SAC_AGENT` ou "user" quando executado pelo usuário

#### Scenario: send — enviar mensagem (sem daemon)
- **WHEN** `sac send <agente> "<corpo>"` é executado e o daemon NÃO está ativo
- **THEN** o sistema cria a mensagem em `inbox/<agente>/`, registra o evento no log, e cutuca o pane com `"SAC: mensagem nova na inbox — rode \`sac next\`"`
- **AND** se o pane do agente não existe, exibe aviso no stderr (mensagem ainda está na inbox)

#### Scenario: send — enviar resposta com reply_to inferido
- **WHEN** o sender tem exatamente 1 tarefa claimed cujo remetente original é o destinatário
- **AND** `sac send <agente> "<corpo>"` é executado
- **THEN** a mensagem é marcada com `reply_to=<id_da_tarefa>` no cabeçalho
- **AND** o daemon entrega a resposta mesmo com tarefa claimed em andamento (fura-fila)

#### Scenario: next — consumir mensagem (com auto-ack de reply)
- **WHEN** `sac next` é executado e a mensagem lida possui `reply_to`
- **THEN** a mensagem é movida diretamente para done (via `store.finish_reply()` ou `store.ack()`)
- **AND** o agente NÃO precisa executar `sac done`
- **AND** NENHUM stale poke será disparado para esta mensagem

#### Scenario: next — consumir mensagem (tarefa sem reply)
- **WHEN** `sac next` é executado e a mensagem NÃO possui `reply_to`
- **AND** o daemon está inativo
- **THEN** a mensagem é movida para claimed (comportamento legado)
- **AND** o agente DEVE executar `sac done <id>` para concluir

#### Scenario: next — consumir mensagem (tarefa com daemon ativo)
- **WHEN** `sac next` é executado e a mensagem NÃO possui `reply_to`
- **AND** o daemon está ativo
- **THEN** a mensagem é movida para done (o daemon entrega tarefas reais direto)
- **AND** o agente NÃO precisa executar `sac done`
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
O sistema SHALL expor o log de eventos para acompanhamento em tempo real, com captura de exceções de leitura para evitar morte do pane, e aguardar o arquivo de log aparecer no boot.

#### Scenario: log — exibir log
- **WHEN** `sac log` é executado
- **THEN** o conteúdo de `.sac/log.jsonl` é exibido
- **AND** `sac log -f` segue o arquivo em tempo real (tail -f)

#### Scenario: log -f aguarda arquivo no boot
- **GIVEN** `.sac/log.jsonl` não existe (sessão nova)
- **WHEN** `sac log -f` é executado
- **THEN** o comando espera o arquivo em loop (sleep 0.5s) até o 1º evento de log ser escrito
- **AND** quando o arquivo aparece, segue normalmente

#### Scenario: Log -f com erro de leitura
- **WHEN** `sac log -f` encontra erro de I/O no arquivo de log
- **THEN** a exceção é capturada e registrada
- **AND** o loop `while True` continua tentando

### Requirement: Injeção de prompt
O sistema SHALL permitir re-injetar o prompt de contrato em agentes específicos.

#### Scenario: inject — re-injetar prompt
- **WHEN** `sac inject <agente>` é executado
- **THEN** o `prompt_file` do agente (se configurado) é re-injetado no pane via paste + Enter

### Requirement: Flag --clean em status (com dry-run)
O sistema SHALL aceitar `sac status --clean` como dry-run (lista órfãos sem remover), exigindo `--yes` para executar a remoção.

#### Scenario: status --clean dry-run
- **WHEN** `sac status --clean` é executado
- **THEN** o sistema identifica agentes órfãos e exibe a lista com contagem de mensagens sem remover nada
- **AND** registra o evento `clean` no log como dry-run (dry_run=true)

#### Scenario: status --clean --yes executa remoção
- **WHEN** `sac status --clean --yes` é executado
- **THEN** os diretórios inbox/claimed órfãos são removidos
- **AND** diretórios done são preservados
- **AND** o evento `clean` é registrado com dry_run=false

#### Scenario: status sem --clean
- **WHEN** `sac status` é executado sem `--clean`
- **THEN** o sistema exibe o status normal sem efetuar limpeza (comportamento inalterado)

### Requirement: Re-check pré-poke no notify_sweep
O sweep `notify_sweep` SHALL re-verificar stale IDs contra claimed antes de enviar cada poke, evitando pokes obsoletos.

#### Scenario: Re-check evita poke falso
- **GIVEN** `stale()` retorna X para agente A
- **AND** X foi done() entre a detecção e o envio
- **WHEN** `notify_sweep` vai pokear A
- **THEN** re-consulta `claimed(A)` e X não está mais lá
- **AND** poke não é enviado

### Requirement: Backoff de poke no notify_sweep
O sweep `notify_sweep` SHALL aplicar backoff exponencial por mensagem, com teto de 5 min, tanto no daemon quanto no legado.

#### Scenario: Backoff no legado
- **GIVEN** `cmd_notify` ativo (legado)
- **WHEN** `notify_sweep` poka a mesma mensagem X repetidamente
- **THEN** o intervalo entre pokes dobra a cada envio (base `poke_stale_after`, teto 300s)

### Requirement: Send para user sem validação de agente
O comando `sac send` SHALL aceitar "user" como destinatário sem validar contra o config, persistindo em `inbox/user/`.

#### Scenario: send para user aceito
- **WHEN** `sac send user "mensagem"` é executado
- **THEN** a mensagem é criada em `inbox/user/` (sem erro de ConfigError)
- **AND** a saída padrão exibe o id da mensagem
- **AND** nenhum poke ou deliver é tentado

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

### Requirement: Comando init — questionário interativo
O sistema SHALL expor o comando `sac init` que guia o usuário na criação de
`sac.toml` e `prompts/*.md` via input()/print().

#### Scenario: init interativo (TTY)
- **GIVEN** diretório sem `sac.toml`
- **AND** stdin é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema pergunta: nome da sessão (default "sac"), socket (Enter vazio = sem socket dedicado), leader (nome, harness, args, prompt_file)
- **AND** para cada worker: nome, harness (kimi/opencode/outro), args, role, boot_wait
- **AND** loops opcionais (nome, sequência de agentes, max_iterations)
- **AND** ao final, gera `sac.toml` no diretório corrente
- **AND** gera `prompts/*.md` com contrato SAC básico para cada agente

#### Scenario: init não interativo (sem TTY)
- **GIVEN** stdin não é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema imprime erro: "modo interativo requer terminal — use --config para apontar um sac.toml existente"
- **AND** retorna exit 1

#### Scenario: init com sac.toml existente
- **GIVEN** `sac.toml` já existe no diretório
- **WHEN** `sac init` é executado
- **THEN** o sistema pergunta se deseja sobrescrever (confirmação)
- **AND** se não, aborta com exit 0

#### Scenario: init valida nomes (charset)
- **GIVEN** usuário digita nome com espaço ou caractere especial
- **WHEN** `sac init` valida o nome
- **THEN** rejeita com "entrada inválida" e repete a pergunta
- **AND** só aceita `[A-Za-z0-9_-]`

#### Scenario: init valida round-trip do TOML gerado
- **GIVEN** todas as respostas coletadas
- **WHEN** o TOML é gerado internamente
- **THEN** o sistema valida o TOML com `tomllib.loads()` antes de escrever
- **AND** se inválido, aborta com erro "TOML gerado é inválido"

#### Scenario: init com prompts existentes
- **GIVEN** diretório `prompts/` já existe com arquivos .md
- **WHEN** `sac init` vai gerar prompts
- **THEN** pergunta se deseja sobrescrever
- **AND** se não, mantém prompts existentes

### Requirement: Progresso no up (TTY only)
O sistema SHALL exibir progresso por agente durante `sac up`, apenas quando
stdout é um terminal (TTY).

#### Scenario: up exibe progresso (TTY)
- **GIVEN** stdout é TTY
- **WHEN** `sac up` cria janelas e injeta prompts
- **THEN** para cada agente imprime `[N/total] nome: ação...`
- **AND** ações incluem "criando janela", "aguardando Xs", "injetando prompt"
- **AND** ao final imprime "sessão no ar com N agentes"

#### Scenario: up sem TTY — silencioso
- **GIVEN** stdout NÃO é TTY (redirecionado)
- **WHEN** `sac up` executa
- **THEN** nenhuma linha de progresso é impressa (apenas a mensagem final)

#### Scenario: up com fail-fast aborta no erro
- **GIVEN** socket com diretório-pai inexistente
- **WHEN** `sac up` tenta criar sessão
- **THEN** o comando ABORTA imediatamente com erro claro
- **AND** imprime sugestão de correção (ex.: "crie o diretório com mkdir -p")
- **AND** retorna exit 1
- **AND** nenhum agente é criado nem prompt injetado

### Requirement: Criação automática do diretório do socket
O sistema SHALL criar o diretório-pai do socket tmux se ele não existir.

#### Scenario: Socket dir criado no up
- **GIVEN** `cfg.socket = "~/.sac-esteira/tmux.sock"`
- **AND** `~/.sac-esteira/` não existe
- **WHEN** `sac up` inicia
- **THEN** o diretório `~/.sac-esteira/` é criado via `mkdir -p`
- **AND** a sessão tmux é criada com sucesso

### Requirement: `sac status --mini` — resumo de uma linha
O subcomando `status` SHALL aceitar a flag `--mini`, que imprime uma única
linha com os contadores de agentes por estado no formato `<n>● <n>!`
(claimed, escalados), omitindo contadores zerados. Se não houver store/sessão
ativo, SHALL imprimir linha vazia e retornar 0 (nunca quebra o `#(...)` do
tmux).

#### Scenario: Agentes claimed e escalados
- **GIVEN** store com 3 agentes claimed e 1 escalado
- **WHEN** `sac status --mini` executa
- **THEN** a saída é `3● 1!`

#### Scenario: Sem contadores
- **GIVEN** store sem agentes claimed nem escalados
- **WHEN** `sac status --mini` executa
- **THEN** a saída é uma linha vazia e o exit code é 0

#### Scenario: Sem store ativo
- **GIVEN** diretório sem `.sac/` inicializado
- **WHEN** `sac status --mini` executa
- **THEN** a saída é uma linha vazia e o exit code é 0

### Requirement: Resolução de config via env da sessão
O sistema SHALL usar o valor da variável de ambiente `SAC_CONFIG` como default do parâmetro `--config`, para que comandos `sac` executados dentro de panes de agente resolvam a configuração da sessão correta independente do cwd.

#### Scenario: SAC_CONFIG definido
- **WHEN** `sac <comando>` é executado sem `--config` e a env `SAC_CONFIG` está definida
- **THEN** a configuração é carregada do caminho em `SAC_CONFIG`, mesmo que o cwd não contenha `sac.toml` (ou contenha outro)

#### Scenario: SAC_CONFIG ausente
- **WHEN** `sac <comando>` é executado sem `--config` e sem `SAC_CONFIG` no ambiente
- **THEN** a configuração é carregada de `./sac.toml` (comportamento atual)

#### Scenario: --config explícito tem precedência
- **WHEN** `sac --config /caminho/x.toml <comando>` é executado com `SAC_CONFIG` definido
- **THEN** a configuração é carregada de `/caminho/x.toml`

