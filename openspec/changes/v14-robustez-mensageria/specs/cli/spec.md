## MODIFIED Requirements

### Requirement: Auto-ack de reply no `sac next`
O comando `sac next` SHALL auto-ackar mensagens com `reply_to` (respostas) ao lê-las, independente de o daemon estar ativo ou não.

#### Scenario: next com reply — auto-ack (independente de daemon)
- **GIVEN** mensagem com `reply_to` em inbox/agente/
- **WHEN** `sac next` é executado
- **THEN** a mensagem é movida para done (via `store.finish_reply()` ou `store.ack()`)
- **AND** o agente NÃO precisa executar `sac done`
- **AND** NENHUM stale poke será disparado para esta mensagem

#### Scenario: next sem reply (tarefa) — claimed com daemon off
- **GIVEN** daemon inativo
- **AND** mensagem SEM `reply_to` em `inbox/agente/`
- **WHEN** `sac next` é executado
- **THEN** a mensagem é movida para claimed (comportamento legado)
- **AND** o agente DEVE executar `sac done <id>` para concluir

#### Scenario: next sem reply (tarefa) — ack com daemon on
- **GIVEN** daemon ativo
- **AND** mensagem SEM `reply_to` em `inbox/agente/`
- **WHEN** `sac next` é executado
- **THEN** a mensagem é movida para done (via `store.ack()`)
- **AND** o agente NÃO precisa executar `sac done` (daemon entrega tarefas reais direto)

### Requirement: Flag --clean em status (com dry-run)
O sistema SHALL oferecer `sac status --clean` como dry-run (lista órfãos sem remover), exigindo `--yes` para executar a remoção.

#### Scenario: status --clean dry-run
- **GIVEN** `.sac/inbox/auditor/` contém mensagens (auditor removido do config)
- **WHEN** `sac status --clean` é executado
- **THEN** o sistema identifica "auditor" como órfão
- **AND** exibe a lista de agentes órfãos e contagem de mensagens sem remover nada
- **AND** registra o evento `clean` no log como dry-run (dry_run=true)

#### Scenario: status --clean --yes executa remoção
- **GIVEN** `.sac/inbox/auditor/` contém mensagens
- **WHEN** `sac status --clean --yes` é executado
- **THEN** o diretório `.sac/inbox/auditor/` é removido
- **AND** `.sac/claimed/auditor/` é removido (se existir)
- **AND** `.sac/done/auditor/` é preservado
- **AND** o evento `clean` é registrado com dry_run=false

#### Scenario: status sem --clean
- **WHEN** `sac status` é executado sem `--clean`
- **THEN** o sistema exibe o status normal sem mencionar órfãos (comportamento inalterado)

### Requirement: Resiliência do log -f no boot
O comando `sac log -f` SHALL aguardar o arquivo `log.jsonl` aparecer, em vez de encerrar com "log vazio".

#### Scenario: log -f wait no boot
- **GIVEN** `.sac/log.jsonl` não existe (sessão nova)
- **WHEN** `sac log -f` é executado
- **THEN** o comando espera o arquivo em loop (sleep 0.5s) até o 1º evento de log ser escrito
- **AND** quando o arquivo aparece, segue normalmente

#### Scenario: log sem -f sem arquivo
- **WHEN** `sac log` (sem -f) e `.sac/log.jsonl` não existe
- **THEN** imprime "log vazio" e retorna 0 (inalterado)

### Requirement: Backoff de poke no notify_sweep
O sweep `notify_sweep` SHALL aplicar backoff exponencial por mensagem, com
teto de 5 min, tanto no daemon quanto no legado.

#### Scenario: Backoff no legado
- **GIVEN** `cmd_notify` ativo (legado)
- **WHEN** `notify_sweep` poka a mesma mensagem X repetidamente
- **THEN** o intervalo entre pokes dobra a cada envio (base poke_stale_after, teto 300s)

### Requirement: Send para user sem validação de agente
O comando `sac send` SHALL aceitar "user" como destinatário sem validar
contra o config, persistindo em `inbox/user/`.

#### Scenario: send para user aceito
- **WHEN** `sac send user "mensagem"` é executado
- **THEN** a mensagem é criada em `inbox/user/` (sem erro de ConfigError)
- **AND** a saída padrão exibe o id da mensagem
- **AND** nenhum poke ou deliver é tentado
O sweep `notify_sweep` SHALL re-verificar stale IDs contra claimed antes de enviar cada poke.

#### Scenario: Re-check evita poke falso
- **GIVEN** `stale()` retorna X para agente A
- **AND** X foi done() entre a detecção e o envio
- **WHEN** `notify_sweep` vai pokear A
- **THEN** re-consulta `claimed(A)` e X não está mais lá
- **AND** poke não é enviado
