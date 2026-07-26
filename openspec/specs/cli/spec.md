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
- **THEN** o sistema renderiza: agentes com marcadores de estado (idle, inbox, working) e atalhos C-b <N>
- **AND** é usado internamente nos panes de sidebar de cada janela (loop `clear; sac sidebar; sleep 5`)

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
`.sac/sac.toml` e `prompts/*.md` via input()/print(), sem exigir leitura de
documentação externa: toda pergunta tem hint com exemplo concreto.

#### Scenario: init interativo (TTY)
- **GIVEN** diretório sem `.sac/sac.toml`
- **AND** stdin é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema abre explicando o que será gerado (`.sac/sac.toml`, `.sac/`, `prompts/*.md`)
- **AND** pergunta: nome da sessão (default "sac", hint com exemplos e onde o nome aparece), socket (hint com exemplo de caminho), boot_wait global (hint com faixa sugerida), número de agentes
- **AND** o agente 1 é anunciado como leader/orquestrador (header + hint do papel) e NÃO recebe pergunta de papel nem de contrato
- **AND** para cada agente 2+: nome, comando (default detectado no PATH — ver Requirement "Detecção de harness no init"), contrato via catálogo (ver Requirement "Catálogo de contratos canônicos"), modelo, boot_wait específico (hint com exemplo)
- **AND** agentes 2+ são `aux` automaticamente (sem pergunta de papel)
- **AND** agrupamento opcional de janelas (ver Requirement "Agrupamento de janelas no init")
- **AND** ao final, gera `.sac/sac.toml` e `prompts/*.md` com o contrato de cada agente
- **AND** ao final do fluxo, instala automaticamente os plugins canônicos (sem pergunta no wizard; falha de rede gera aviso orientando `sac plugins install`, sem abortar)
- **AND** imprime checklist de próximos passos atualizado com os novos caminhos (sem passo de plugins — é automático)

#### Scenario: init não interativo (sem TTY)
- **GIVEN** stdin não é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema imprime erro: "modo interativo requer terminal — use --config para apontar um sac.toml existente"
- **AND** retorna exit 1

#### Scenario: init com sac.toml existente
- **GIVEN** `.sac/sac.toml` ou `sac.toml` já existe no diretório
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

### Requirement: Comando doctor — diagnóstico do ambiente

O sistema SHALL expor o comando `sac doctor` que verifica os pré-requisitos do
ambiente e reporta OK/FALHA por item com orientação de correção. O comando é
read-only (sem side-effects). Exit 0 se todos os itens essenciais estão OK;
exit 1 se algum item essencial falhar. Itens não essenciais (warning) não
alteram o exit code.

#### Checklist de verificação

| Item | Essencial | Critério |
|------|-----------|----------|
| Python version | sim | >= 3.11 |
| tmux presence | sim | `shutil.which("tmux")` não nulo |
| tmux version | sim | `tmux -V` retorna versão >= 3.2 (o layout grid exige) |
| Socket dir writable | sim | se `socket` configurado, diretório-pai existe e é gravável |
| Config loads | sim | config resolvido pela cadeia de descoberta é parseável sem erro; saída indica qual arquivo foi usado |
| Harnesses in PATH | não | cada `command` dos agentes em `[[agents]]` existe no PATH (warning individual) |
| Legado ignorado | não | `./sac.toml` existe na raiz (warning: fallback removido — mover para `.sac/` ou apagar) |
| openspec CLI | não | `shutil.which("openspec")` não nulo (warning com orientação de instalação — stack canônica) |
| Plugins canônicos | não | superpowers/rtk/openspec em `$SAC_HOME/plugins` na ref pinada, bins em `$SAC_HOME/bin` (ver spec plugins-canonicos) |

#### Formato de saída

```
[OK]  Python 3.12.5
[OK]  tmux 3.4
[OK]  openspec found in PATH
[OK]  socket dir ~/.sac-esteira is writable
[OK]  config loads (.sac/sac.toml, 3 agents)
[OK]  plugin superpowers @ v6.1.1
[WARN] plugin rtk não instalado — rode 'sac plugins install'
[WARN] harness 'kimi' not found in PATH (config may be for another machine)
[WARN] ./sac.toml existe na raiz mas é ignorado (fallback removido) — mova para .sac/ ou apague
```

Itens essenciais com FALHA usam `[FAIL]` e incluem orientação de correção:

```
[FAIL] tmux not found — install with: apt install tmux / brew install tmux
[FAIL] Python 3.10.2 < 3.11 — upgrade Python to 3.11+
```

#### Scenario: doctor — tudo OK

- **GIVEN** ambiente com Python >= 3.11, tmux >= 3.2, socket válido, config
  válida, todos os harnesses no PATH
- **WHEN** `sac doctor` é executado
- **THEN** todos os itens reportam `[OK]`
- **AND** exit code é 0

#### Scenario: doctor — tmux ausente (essencial)

- **GIVEN** `shutil.which("tmux")` retorna None
- **WHEN** `sac doctor` é executado
- **THEN** o item tmux reporta `[FAIL]` com orientação de instalação
- **AND** exit code é 1

#### Scenario: doctor — Python version insuficiente

- **GIVEN** `sys.version_info < (3, 11)`
- **WHEN** `sac doctor` é executado
- **THEN** o item Python reporta `[FAIL]` com upgrade instructions
- **AND** exit code é 1

#### Scenario: doctor — harness ausente (não essencial)

- **GIVEN** config com `command = "kimi"` e `shutil.which("kimi")` é None
- **WHEN** `sac doctor` é executado
- **THEN** o item do harness reporta `[WARN]` (não `[FAIL]`)
- **AND** exit code permanece 0 (outros itens essenciais OK)

#### Scenario: doctor — sem config (não essencial)

- **GIVEN** diretório sem config em nenhum caminho da cadeia e sem `$SAC_CONFIG`
- **WHEN** `sac doctor` é executado
- **THEN** itens independentes de config (Python, tmux) rodam normalmente
- **AND** o item config reporta `[WARN]` (config não encontrada, ignorando
  checagens dependentes)
- **AND** se `./sac.toml` existir na raiz, o aviso inclui orientação de migração
- **AND** items dependentes de config (socket, harnesses) são pulados/silenciados
- **AND** exit code é 0

#### Scenario: doctor — config ambíguo (não essencial)

- **GIVEN** `./.sac/sac.toml` e `./sac.toml` existem no diretório
- **WHEN** `sac doctor` é executado
- **THEN** o item config indica qual arquivo foi usado (`.sac/sac.toml`)
- **AND** um `[WARN]` informa que o `./sac.toml` da raiz é ignorado (fallback
  removido) e orienta mover para `.sac/` ou apagar

#### Scenario: doctor — openspec ausente (não essencial)

- **GIVEN** `shutil.which("openspec")` retorna None
- **WHEN** `sac doctor` é executado
- **THEN** o item openspec reporta `[WARN]` com orientação de instalação
- **AND** exit code permanece 0

#### Scenario: doctor — tmux version < 3.2

- **GIVEN** `tmux -V` retorna "tmux 3.1"
- **WHEN** `sac doctor` é executado
- **THEN** o item tmux version reporta `[FAIL]` com upgrade instructions
- **AND** exit code é 1

#### Scenario: doctor — sem side-effects

- **WHEN** `sac doctor` é executado
- **THEN** nenhum arquivo é criado, modificado ou removido
- **AND** nenhum processo tmux é iniciado ou terminado
- **AND** nenhum dado de mensageria é alterado

### Requirement: Detecção de harness no init
O sistema SHALL detectar harnesses instalados no PATH durante o `sac init` e
oferecer o primeiro encontrado como default da pergunta de comando, na ordem
de preferência: `kimi` → `opencode` → `claude`. Se nenhum for encontrado, o
default é o placeholder fixo ("kimi" para o agente 1, "opencode" para os
demais). A validação com warning da v22 (comando ausente → corrigir ou
seguir) é mantida para qualquer resposta.

#### Scenario: harness detectado vira default
- **GIVEN** `shutil.which("kimi")` retorna um caminho
- **WHEN** o wizard pergunta o comando de um agente
- **THEN** o default exibido é `kimi` e o hint indica "detectado no seu PATH"

#### Scenario: preferência da ordem canônica
- **GIVEN** `opencode` e `claude` no PATH, `kimi` ausente
- **WHEN** o wizard pergunta o comando
- **THEN** o default exibido é `opencode`

#### Scenario: nenhum harness detectado
- **GIVEN** nenhum dos harnesses canônicos no PATH
- **WHEN** o wizard pergunta o comando
- **THEN** o default é o placeholder fixo e nenhum hint de detecção é exibido

### Requirement: Catálogo de contratos canônicos
O sistema SHALL embutir um catálogo de contratos de papel (dados, em módulo
próprio) usado pelo `sac init`: líder/orquestrador, desenvolvedor, revisor de
código, documentação, deploy/release, segurança e auxiliar genérico. Todo
contrato inclui o protocolo de mensageria SAC (inbox/`sac next`/reply/
`sac done`) mais a disciplina do papel, em texto puro que NÃO exige plugin ou
CLI externo instalado. O contrato de líder SHALL incluir disciplina de
delegação e ciclo de revisão: decompor e delegar com `sac send`, cobrar
revisão do trabalho dos auxiliares, iterar até convergir e escalar ao usuário
só em bloqueio real (substitui os loops declarados, removidos na v26b). O
agente 1 recebe o contrato de líder sem pergunta; agentes 2+ escolhem em lista
numerada que EXCLUI o papel de líder (só pode haver um líder — o agente 1),
com default "desenvolvedor". O contrato gerado em `prompts/<nome>.md` é
editável pelo usuário depois do init.

#### Scenario: agente 1 recebe contrato de líder sem pergunta
- **GIVEN** o wizard configurando o agente 1
- **WHEN** o init gera os prompts
- **THEN** `prompts/<nome>.md` do agente 1 contém o contrato de líder/orquestrador
- **AND** contém a disciplina de delegação e ciclo de revisão
- **AND** nenhuma pergunta de catálogo foi feita para o agente 1

#### Scenario: catálogo numerado para agentes aux
- **GIVEN** o wizard configurando o agente 2
- **WHEN** a pergunta de contrato é exibida
- **THEN** a lista numerada NÃO contém "líder/orquestrador"
- **AND** aparece com default "desenvolvedor"
- **AND** Enter seleciona o default

#### Scenario: escolha inválida repete a pergunta
- **GIVEN** o usuário digita um número fora da lista ou texto inválido
- **WHEN** o wizard valida a escolha
- **THEN** rejeita e repete a pergunta

#### Scenario: contrato contém mensageria + disciplina
- **GIVEN** o usuário escolheu "revisor de código" para o agente 2
- **WHEN** o init gera `prompts/<nome>.md`
- **THEN** o arquivo contém o protocolo de mensageria SAC e a disciplina de
  revisão por evidência (bloqueantes vs. warnings)
- **AND** não contém dependência de plugin ou CLI externo para ser seguido

### Requirement: Agrupamento de janelas no init
O sistema SHALL perguntar ao final do questionário se o usuário deseja
agrupar agentes em janelas `[windows]` (default: não). Se sim, o wizard coleta
por janela: nome (validado), agentes (nomes separados por espaço, validados
contra os agentes criados) e disposição (`;` lado a lado ou `,` empilhados),
exibindo preview do resultado parcial antes de perguntar se deseja adicionar
outra janela. Agentes fora de qualquer janela mantêm janela própria.

#### Scenario: resposta "não" não gera [windows]
- **GIVEN** o usuário responde "n" ao agrupamento
- **WHEN** o config é gerado
- **THEN** o TOML não contém seção `[windows]`

#### Scenario: janela lado a lado
- **GIVEN** agentes `dev-1` e `dev-2` criados
- **WHEN** o usuário define a janela `dev` com "dev-1 dev-2" e disposição lado a lado
- **THEN** o TOML contém `[windows]` com `dev = "dev-1;dev-2"`

#### Scenario: agente desconhecido é rejeitado
- **GIVEN** o usuário digita um nome de agente inexistente na janela
- **WHEN** o wizard valida
- **THEN** rejeita com mensagem indicando os nomes válidos e repete a pergunta

#### Scenario: agentes fora de janelas mantêm janela própria
- **GIVEN** 3 agentes criados e apenas 2 agrupados em uma janela
- **WHEN** o config é gerado
- **THEN** o agente não agrupado continua com janela própria (comportamento default)

### Requirement: Comando uninstall — remoção segura da configuração
O sistema SHALL expor o comando `sac uninstall` que remove a configuração do
SAC no workspace atual de forma segura e confirmada: `.sac/` (config e
estado), `prompts/` e o `sac.toml` legado da raiz, se existir. O comando
recusa se a sessão tmux do config estiver no ar e exige confirmação digitando
o nome da sessão. Nada fora do diretório do workspace é removido.

#### Scenario: sessão no ar — recusa
- **GIVEN** a sessão tmux definida no config está ativa
- **WHEN** `sac uninstall` é executado
- **THEN** o sistema recusa com mensagem orientando `sac down` antes
- **AND** nada é removido
- **AND** retorna exit 1

#### Scenario: confirmação incorreta aborta
- **GIVEN** a sessão não está no ar
- **WHEN** o usuário digita algo diferente do nome da sessão na confirmação
- **THEN** o sistema aborta sem remover nada
- **AND** retorna exit 0

#### Scenario: confirmação correta remove
- **GIVEN** a sessão não está no ar e o usuário digita o nome da sessão
- **WHEN** `sac uninstall` é executado
- **THEN** o sistema lista o que será removido antes da confirmação
- **AND** remove `.sac/`, `prompts/` e `sac.toml` legado (se existir)
- **AND** nenhum arquivo fora do workspace é tocado
- **AND** retorna exit 0

#### Scenario: nada configurado
- **GIVEN** diretório sem `.sac/`, sem `prompts/` e sem `sac.toml`
- **WHEN** `sac uninstall` é executado
- **THEN** o sistema informa que não há nada para remover
- **AND** retorna exit 0

### Requirement: Descoberta de config
O sistema SHALL resolver o caminho do config pela ordem de precedência:
`--config` (flag explícita) > `$SAC_CONFIG` > `./.sac/sac.toml`. Nenhum outro
caminho é considerado — `./sac.toml` na raiz é ignorado. `sac up` SHALL
exportar `SAC_CONFIG` com o caminho efetivamente usado.

#### Scenario: SAC_CONFIG definido
- **WHEN** `sac <comando>` é executado sem `--config` e a env `SAC_CONFIG` está definida
- **THEN** a configuração é carregada do caminho em `SAC_CONFIG`, mesmo que o cwd não contenha config (ou contenha outro)

#### Scenario: Config oculto encontrado no diretório
- **WHEN** `./.sac/sac.toml` existe e não há `--config` nem `SAC_CONFIG`
- **THEN** a configuração é carregada de `./.sac/sac.toml`

#### Scenario: Legado na raiz é ignorado
- **WHEN** apenas `./sac.toml` existe (sem `.sac/sac.toml`) e não há `--config` nem `SAC_CONFIG`
- **THEN** o sistema NÃO carrega o legado
- **AND** imprime erro orientando a migração (`mkdir -p .sac && mv sac.toml .sac/`) ou `sac init`
- **AND** retorna exit 1

#### Scenario: --config explícito tem precedência
- **WHEN** `sac --config /caminho/x.toml <comando>` é executado com `SAC_CONFIG` definido
- **THEN** a configuração é carregada de `/caminho/x.toml`

#### Scenario: Nenhum config encontrado
- **WHEN** nenhum dos caminhos da cadeia existe
- **THEN** o sistema imprime erro indicando os caminhos tentados e sugere `sac init`
- **AND** retorna exit 1

### Requirement: Sugestão de modelos por harness no init
Na pergunta "Modelo" do `sac init`, o sistema SHALL tentar listar os modelos
válidos do harness escolhido: para `kimi`, os aliases das tabelas
`[models."<alias>"]` de `~/.kimi-code/config.toml` (via tomllib — apenas nomes
de tabelas); para `opencode`, a saída de `opencode models` (com timeout
curto). Se a listagem falhar ou o harness for desconhecido, a pergunta cai no
modo texto livre. Com lista disponível, a resposta é o número do modelo ou
Enter (vazio = não passar `--model`).

#### Scenario: kimi lista aliases do config do usuário
- **GIVEN** o harness escolhido é `kimi` e `~/.kimi-code/config.toml` contém
  tabelas `[models."kimi-code/k3"]` e `[models."esteira/k3"]`
- **WHEN** a pergunta de modelo é exibida
- **THEN** a lista numerada contém `kimi-code/k3` e `esteira/k3`

#### Scenario: opencode lista modelos ao vivo
- **GIVEN** o harness escolhido é `opencode` e `opencode models` retorna
  linhas `opencode/big-pickle`, `opencode/claude-opus-5`
- **WHEN** a pergunta de modelo é exibida
- **THEN** a lista numerada contém esses modelos

#### Scenario: resposta por número
- **GIVEN** a lista de modelos exibida
- **WHEN** o usuário responde um número válido da lista
- **THEN** o modelo correspondente é usado (args `--model <modelo>`)
- **AND** número fora da lista repete a pergunta

#### Scenario: Enter não passa --model
- **GIVEN** a lista de modelos exibida
- **WHEN** o usuário responde vazio
- **THEN** o agente é configurado sem `--model` (default do harness)

#### Scenario: fallback para texto livre
- **GIVEN** harness desconhecido ou falha na listagem (arquivo ausente,
  timeout, erro de parse)
- **WHEN** a pergunta de modelo é exibida
- **THEN** nenhuma lista é mostrada e a resposta é texto livre (comportamento
  anterior), sem erro para o usuário

### Requirement: Comando approve
O sistema SHALL expor o comando `sac approve <id>` para aprovar uma solicitação de aprovação pendente, executável de qualquer pane/diretório com acesso ao SAC_ROOT.

#### Scenario: Approve de approval_request
- **WHEN** `sac approve <id>` é executado para uma approval_request pendente
- **THEN** o estado muda para `approved`
- **AND** o líder recebe reply automática com veredito APROVADO

#### Scenario: Approve de mensagem sem ser approval_request
- **WHEN** `sac approve <id>` é executado para uma mensagem comum
- **THEN** o sistema retorna erro: "mensagem <id> não é uma approval_request"

### Requirement: Comando respond
O sistema SHALL expor o comando `sac respond <id> <veredito> [motivo]` para responder a uma solicitação de aprovação.

#### Scenario: Respond com APPROVED
- **WHEN** `sac respond <id> "APPROVED" "Pode prosseguir"` é executado
- **THEN** o estado muda para `approved` e o líder recebe reply

#### Scenario: Respond com REJECTED
- **WHEN** `sac respond <id> "REJECTED" "Fora do escopo"`
- **THEN** o estado muda para `rejected` e o líder recebe reply com motivo

#### Scenario: Respond com veredito inválido
- **WHEN** `sac respond <id> "INVALIDO"` é executado
- **THEN** o sistema rejeita com erro: "veredito deve ser APPROVED ou REJECTED"

### Requirement: Flag --approval no comando send
O comando send SHALL aceitar a flag `--approval` (apenas para o líder) para criar uma approval_request destinada ao `user`.

#### Scenario: send --approval pelo líder
- **WHEN** o líder executa `sac send user "Podemos fazer deploy?" --approval`
- **THEN** a mensagem é criada como `type: approval_request` na inbox do user

#### Scenario: send --approval por agente não-líder
- **WHEN** um agente aux tenta `sac send user "..." --approval`
- **THEN** o sistema rejeita com erro: "apenas o leader pode enviar approval_request"

