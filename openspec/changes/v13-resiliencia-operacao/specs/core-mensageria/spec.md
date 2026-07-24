## MODIFIED Requirements

### Requirement: Log auditável append-only
O sistema SHALL manter um log JSONL de todos os eventos de mensageria para auditoria e depuração, incluindo eventos de erro nos loops.

#### Scenario: Eventos registrados
- **WHEN** mensagens são enviadas, consumidas, concluídas, agentes são cutucados, o daemon entrega/re-cutuca, ou ocorre erro em loop
- **THEN** cada evento é registrado como uma linha JSON em `.sac/log.jsonl` com timestamp e campos específicos do evento
- **AND** eventos `send` incluem sender e destinatário
- **AND** eventos `next` e `done` incluem agent e id
- **AND** eventos `poke` incluem agent e contagem de mensagens
- **AND** eventos `deliver` (daemon) incluem agent, id e sender
- **AND** eventos `loop_error` incluem o agente e a mensagem de erro (string do exception)

## ADDED Requirements

### Requirement: Notify resiliente — loop com try/except
O loop `sac notify` SHALL capturar exceções no sweep de stale detection para evitar morte silenciosa do processo.

#### Scenario: Notify sweep lança exceção
- **GIVEN** um agente cujo `store.stale()` lança exceção (ex.: corrupção de filesystem)
- **WHEN** `sac notify` (ou `sac daemon`) executa o sweep
- **THEN** a exceção é capturada por try/except genérico
- **AND** o evento `loop_error` é registrado em `log.jsonl` com o agente e o erro
- **AND** o loop continua para o próximo agente (não aborta)

#### Scenario: Log -f com exceção de leitura
- **WHEN** `sac log -f` encontra erro de leitura no arquivo (ex.: rotação de log)
- **THEN** a exceção é capturada e registrada via `store.log("loop_error")`
- **AND** o loop continua (não aborta)

### Requirement: Limpeza de mensagens órfãs
O sistema SHALL permitir remover mensagens de agentes não declarados no `sac.toml` e inbox do "user" sem agente correspondente.

#### Scenario: Limpeza de inbox de agente removido
- **GIVEN** `sac.toml` declara agentes A e B
- **AND** `.sac/inbox/C/` contém mensagens (agente C foi removido do config)
- **WHEN** `sac status --clean` é executado
- **THEN** o diretório `.sac/inbox/C/` é removido
- **AND** o diretório `.sac/claimed/C/` é removido (se existir)
- **AND** o diretório `.sac/done/C/` é preservado (histórico)

#### Scenario: Limpeza de inbox do "user"
- **GIVEN** `.sac/inbox/user/` contém mensagens
- **WHEN** `sac status --clean` é executado
- **THEN** o diretório `.sac/inbox/user/` é removido
- **AND** o evento `clean` é registrado em `log.jsonl` com contagem de mensagens removidas

#### Scenario: Nenhuma inbox órfã — sem ação
- **GIVEN** todos os diretórios em `.sac/inbox/` correspondem a agentes declarados
- **WHEN** `sac status --clean` é executado
- **THEN** nenhum diretório é removido
- **AND** o sistema informa que não há órfãos
