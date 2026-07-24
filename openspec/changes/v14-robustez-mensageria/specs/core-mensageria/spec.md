## ADDED Requirements

### Requirement: Marcação de reply no envio
O sistema SHALL inferir e persistir o campo `reply_to` no momento do `store.send()` para distinguir replies de tarefas.

#### Scenario: Send detecta reply automaticamente
- **GIVEN** dev-1 tem exatamente 1 tarefa claimed de leader (id `T001`)
- **WHEN** dev-1 executa `sac send leader "pronto"`
- **THEN** a mensagem gerada contém o cabeçalho `reply_to: T001`
- **AND** o evento `send` em `log.jsonl` não inclui reply_to (rastreabilidade via arquivo)

#### Scenario: Send sem claimed — sem reply_to (tarefa)
- **GIVEN** dev-1 não tem mensagens claimed
- **WHEN** dev-1 executa `sac send leader "msg"`
- **THEN** a mensagem NÃO contém cabeçalho `reply_to`
- **AND** é tratada como tarefa

#### Scenario: Múltiplas claimed — match pela mais recente
- **GIVEN** dev-1 tem 2 tarefas claimed: de auditor (mais antiga, id `T001`) e de leader (mais recente, id `T002`)
- **WHEN** dev-1 executa `sac send leader "pronto"`
- **THEN** a mensagem contém `reply_to: T002` (match pela claimed mais recente cujo sender é leader)
- **AND** o envio é tratado como reply, não como tarefa

#### Scenario: arquivo .msg com reply_to é parseado corretamente
- **GIVEN** arquivo `.msg` com cabeçalho `reply_to: T001`
- **WHEN** `Store._parse()` lê o arquivo
- **THEN** `Message.reply_to == "T001"`

#### Scenario: arquivo .msg antigo sem reply_to — reply_to = None
- **GIVEN** arquivo `.msg` sem cabeçalho `reply_to` (criado antes da v1.4)
- **WHEN** `Store._parse()` lê o arquivo
- **THEN** `Message.reply_to is None`
- **AND** a mensagem é tratada como tarefa (compatibilidade retroativa)

### Requirement: Daemon entrega reply sem exigir done
O daemon SHALL entregar mensagens com `reply_to` sem movê-las para claimed — após o paste, vão direto para done/.

#### Scenario: Daemon entrega reply → deliver_reply
- **GIVEN** mensagem com `reply_to` em `inbox/leader/`
- **WHEN** o daemon executa `_deliver_next("leader")`
- **THEN** a mensagem é movida para claimed (via `store.next()`)
- **AND** após o paste, é movida para done/ via `store.finish_reply()`
- **AND** o evento `deliver_reply` é registrado em `log.jsonl`
- **AND** a mensagem NUNCA aparecerá em stale pokes

#### Scenario: Daemon entrega tarefa (sem reply_to) — claimed (inalterado)
- **GIVEN** mensagem SEM `reply_to` em `inbox/dev-1/`
- **WHEN** o daemon executa `_deliver_next("dev-1")`
- **THEN** a mensagem permanece em claimed após a entrega
- **AND** o evento `deliver` é registrado (inalterado)
- **AND** stale pokes podem ocorrer se `sac done` não for executado

### Requirement: Reply lida manualmente no legado é auto-ackada
No modo legado (sem daemon), `sac next` SHALL auto-ackar mensagens com `reply_to` ao lê-las.

#### Scenario: next sem daemon + reply → auto-ack
- **GIVEN** daemon inativo
- **AND** mensagem com `reply_to` em `inbox/leader/`
- **WHEN** `sac next` é executado (via `cmd_next`)
- **THEN** a mensagem é movida para claimed (via `store.next()`)
- **AND** imediatamente movida para done/ via `store.finish_reply()`
- **AND** o agente NÃO precisa executar `sac done`

#### Scenario: next sem daemon + tarefa (sem reply_to) — claimed (inalterado)
- **GIVEN** daemon inativo
- **AND** mensagem SEM `reply_to` em `inbox/dev-1/`
- **WHEN** `sac next` é executado
- **THEN** a mensagem permanece em claimed (comportamento legado)
- **AND** o agente DEVE executar `sac done`

### Requirement: Reply cut queue — entrega imediata mesmo com claimed
O daemon SHALL entregar mensagens com `reply_to` imediatamente, mesmo que o
agente tenha tarefa claimed em andamento.

#### Scenario: Daemon entrega reply com claimed ocupado
- **GIVEN** agente com 1 tarefa claimed (em andamento)
- **AND** mensagem com `reply_to` em `inbox/<agente>/`
- **WHEN** o daemon executa `_process_agent("<agente>")`
- **THEN** o daemon entrega a reply via paste (mesmo com claimed)
- **AND** a reply vai para done/ via finish_reply
- **AND** a tarefa claimed original permanece em claimed (não afetada)

#### Scenario: Daemon NÃO entrega tarefa com claimed ocupado
- **GIVEN** agente com 1 tarefa claimed
- **AND** mensagem SEM `reply_to` em inbox
- **WHEN** o daemon executa `_process_agent`
- **THEN** a tarefa NÃO é entregue (serialização: agente já ocupado)

#### Scenario: Peek detecta reply sem consumir
- **GIVEN** mensagem com `reply_to` em inbox/agente/
- **WHEN** `store.peek_next(agent)` é chamado
- **THEN** retorna `(id, reply_to_value)` sem mover o arquivo
- **AND** a mensagem permanece em inbox/

#### Scenario: Peek sem pending retorna None
- **GIVEN** inbox do agente vazia
- **WHEN** `store.peek_next(agent)` é chamado
- **THEN** retorna None

### Requirement: Rota para user
O sistema SHALL aceitar `sac send user "<msg>"` sem validar "user" como agente
do config, persistindo a mensagem em `inbox/user/`.

#### Scenario: Send para user sem validação
- **GIVEN** "user" não está em `[[agents]]` no sac.toml
- **WHEN** `sac send user "mensagem"` é executado
- **THEN** a mensagem é criada em `inbox/user/`
- **AND** NENHUM poke ou deliver é tentado (não há pane do user)
- **AND** o evento `send` é registrado em `log.jsonl`

#### Scenario: Leitura da inbox do user
- **GIVEN** `.sac/inbox/user/` contém mensagens
- **WHEN** o usuário executa `sac log`
- **THEN** as mensagens são visíveis (eventos `send` no log apontam o destinatário "user")
- **AND** opcionalmente: `SAC_AGENT=user sac next` lê a mensagem

### Requirement: Backoff exponencial de poke
O daemon (e notify_sweep legado) SHALL aplicar intervalo exponencial entre
pokes à mesma mensagem, com teto de 5 minutos.

#### Scenario: Backoff dobra intervalo
- **GIVEN** mensagem X stale em claimed/agente/ com `poke_stale_after=10`
- **WHEN** o daemon poka X (1º poke)
- **THEN** o próximo poke a X só será enviado após 20s (10×2)
- **AND** o 3º após 40s, 4º após 80s, até teto 600s (10 min)

#### Scenario: Backoff por mensagem (independente)
- **GIVEN** mensagens X e Y stale no mesmo agente
- **WHEN** X é pokada 2× e Y é pokada 1×
- **THEN** X tem intervalo de 40s (10×2×2) e Y de 20s (10×2)
- **AND** cada mensagem tem seu próprio contador

#### Scenario: Backoff reseta ao reiniciar daemon
- **GIVEN** daemon ativo com backoff já elevado para msg X
- **WHEN** o daemon reinicia (cai e sobe)
- **THEN** o estado de backoff é perdido (em memória)
- **AND** o 1º poke pós-reinício usa o intervalo base (poke_stale_after)

#### Scenario: notify_sweep legado aplica mesmo backoff
- **GIVEN** `cmd_notify` ativo (legado, sem daemon)
- **WHEN** `notify_sweep` poka mensagem X
- **THEN** o intervalo dobra a cada poke, mesmo comportamento do daemon
Mensagens em inbox ou claimed há mais de `poke_stale_after` segundos SHALL ser detectadas para re-cutucada do agente. O reply marking reduz a incidência de mensagens em claimed (replies saem de claimed em <100ms via daemon ou CLI).

#### Scenario: Identificação de mensagens stale — inbox
- **GIVEN** mensagem em inbox/agente/ há mais de `poke_stale_after` segundos
- **WHEN** stale detection é executada (daemon ou notify)
- **THEN** a mensagem é identificada como stale
- **AND** o agente é re-cutucado

#### Scenario: Identificação de mensagens stale — claimed (tarefas reais)
- **GIVEN** mensagem em claimed/agente/ há mais de `poke_stale_after` segundos
- **AND** a mensagem foi colocada em claimed pelo daemon (tarefa real, sem reply_to)
- **WHEN** stale detection é executada
- **THEN** a mensagem é identificada como stale
- **AND** o agente é re-cutucado com lembrete de `sac done`

### Requirement: Resiliência do log -f no boot
`sac log -f` SHALL aguardar o arquivo `log.jsonl` aparecer, em vez de retornar "log vazio" e encerrar.

#### Scenario: log -f sem arquivo existente
- **GIVEN** `.sac/log.jsonl` não existe
- **WHEN** `sac log -f` é executado
- **THEN** o comando entra em loop aguardando o arquivo aparecer (sleep 0.5s entre tentativas)
- **AND** não imprime "log vazio" nem retorna 0 até o arquivo existir
- **AND** quando o arquivo aparece, começa a seguir normalmente

#### Scenario: log sem -f sem arquivo existente
- **GIVEN** `.sac/log.jsonl` não existe
- **WHEN** `sac log` (sem -f) é executado
- **THEN** o sistema imprime "log vazio" e retorna 0 (comportamento inalterado)

### Requirement: Re-check pré-poke
O sistema SHALL re-verificar claimed imediatamente antes de enviar um poke, para evitar poke obsoleto se o agente fez `sac done` entre a detecção de stale e o envio.

#### Scenario: Re-check evita poke obsoleto
- **GIVEN** `store.stale()` identifica mensagem X como stale em claimed
- **AND** entre a detecção e o envio, o agente executa `sac done X`
- **WHEN** `notify_sweep` tenta enviar o poke
- **THEN** a mensagem X não está mais em claimed
- **AND** NENHUM poke é enviado para X
