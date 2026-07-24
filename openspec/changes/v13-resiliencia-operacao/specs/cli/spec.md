## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Resiliência em loops — try/except em cmd_notify
O comando `sac notify` SHALL capturar exceções no loop de sweep para evitar morte silenciosa.

#### Scenario: Notify com try/except (já coberto em core-mensageria)
- **WHEN** `sac notify` roda e `notify_sweep` lança exceção
- **THEN** a exceção é capturada e registrada via `store.log("loop_error")`
- **AND** o loop continua

### Requirement: Resiliência em cmd_log -f
O comando `sac log -f` SHALL capturar exceções de leitura para evitar morte do pane.

#### Scenario: Log -f com erro de leitura
- **WHEN** `sac log -f` encontra erro de I/O no arquivo de log
- **THEN** a exceção é capturada e registrada
- **AND** o loop `while True` continua tentando

### Requirement: Flag --clean em status
O sistema SHALL aceitar `sac status --clean` para gatilhar limpeza de mensagens órfãs.

#### Scenario: status --clean
- **WHEN** `sac status --clean` é executado
- **THEN** o sistema executa a limpeza de órfãos (ver core-mensageria)
- **AND** exibe o resultado da limpeza junto com o status normal

#### Scenario: status sem --clean
- **WHEN** `sac status` é executado sem `--clean`
- **THEN** o sistema exibe o status normal sem efetuar limpeza (comportamento inalterado)
