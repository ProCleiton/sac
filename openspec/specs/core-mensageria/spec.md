# Core Mensageria

## Purpose
Sistema de mensageria baseado em filesystem para coordenação multi-agente. A "central" é o diretório `.sac/` com subdiretórios `inbox/<agente>/`, `claimed/<agente>/`, `done/<agente>/` e o arquivo `log.jsonl`. Agentes comunicam-se escrevendo/consumindo arquivos `.msg` — sem daemon, banco ou fila em memória. O contrato de conclusão é explícito: sentinela `SAC_DONE` + comando `sac done`.

## Requirements
### Requirement: Armazenamento persistente de mensagens
O sistema SHALL armazenar mensagens como arquivos individuais no filesystem, sem dependência de banco ou processo em execução.

#### Scenario: Envio de mensagem
- **WHEN** uma mensagem é enviada via `sac send <agente> "<corpo>"`
- **THEN** um arquivo `<YYYYMMDD>-<HHMMSS>-<NNN>-from-<sender>.msg` é criado em `inbox/<agente>/` com cabeçalho (id, from, to, ts) e corpo
- **AND** o evento `send` é registrado em `log.jsonl` com timestamp, sender, destinatário e id

#### Scenario: Consumo de mensagem (FIFO)
- **WHEN** um agente executa `sac next`
- **THEN** a mensagem mais antiga (ordem alfabética do nome do arquivo) é movida de `inbox/<agente>/` para `claimed/<agente>/`
- **AND** seu id e conteúdo são impressos na saída padrão
- **AND** o evento `next` é registrado em `log.jsonl`

#### Scenario: Conclusão de mensagem
- **WHEN** um agente executa `sac done <id> "<resumo>"`
- **THEN** a mensagem é movida de `claimed/<agente>/` para `done/<agente>/`
- **AND** o evento `done` é registrado em `log.jsonl` com id e resumo

#### Scenario: Mensagem sem claim
- **WHEN** `sac done <id>` é executado para uma mensagem que não está em `claimed/` do agente
- **THEN** o sistema retorna erro informando que a mensagem não está em posse do agente

#### Scenario: next sem mensagens
- **WHEN** `sac next` é executado e `inbox/<agente>/` está vazio
- **THEN** o sistema retorna indicando que não há mensagens (não bloqueia)

### Requirement: IDs sequenciais com timestamp
O identificador de mensagem SHALL conter timestamp e sequencial para ordenação FIFO natural e rastreabilidade.

#### Scenario: Formato do ID
- **GIVEN** uma mensagem enviada em 24/07/2026 às 10:00:00 como 1ª do segundo
- **THEN** o ID gerado é `20260724-100000-001-from-<sender>`
- **AND** IDs no mesmo segundo recebem sequenciais incrementais (002, 003...)

### Requirement: Log auditável append-only
O sistema SHALL manter um log JSONL de todos os eventos de mensageria para auditoria e depuração.

#### Scenario: Eventos registrados
- **WHEN** mensagens são enviadas, consumidas, concluídas ou agentes são cutucados
- **THEN** cada evento é registrado como uma linha JSON em `.sac/log.jsonl` com timestamp e campos específicos do evento
- **AND** eventos `send` incluem sender e destinatário
- **AND** eventos `next` e `done` incluem agent e id
- **AND** eventos `poke` incluem agent e contagem de mensagens

### Requirement: Sentinela de conclusão SAC_DONE
As respostas dos agentes SHALL ser delimitadas por uma sentinela explícita para detecção precisa de fim de processamento.

#### Scenario: Resposta concluída
- **WHEN** um agente termina seu processamento
- **THEN** sua última linha de saída contém apenas `SAC_DONE`
- **AND** `sac recv <agente>` extrai o texto anterior à sentinela como resposta completa
- **AND** `sac recv` retorna exit 0 indicando conclusão

#### Scenario: Resposta em andamento
- **WHEN** `sac recv <agente>` é executado e a sentinela `SAC_DONE` não está presente
- **THEN** o sistema retorna os últimos 500 caracteres e exit 1, indicando processamento em andamento

### Requirement: Stale detection (re-poke)
Mensagens esquecidas (pending ou claimed sem `sac done` há mais de `poke_stale_after` segundos) SHALL ser detectadas para re-cutucada do agente.

#### Scenario: Identificação de mensagens stale
- **WHEN** `sac notify` varre inbox/claimed de todos agentes
- **THEN** mensagens com idade > `poke_stale_after` segundos são identificadas
- **AND** o agente é re-cutucado com notificação
- **AND** o evento `poke` é registrado em `log.jsonl`

### Requirement: Reply-to-sender
Respostas de agentes SHALL ser enviadas de volta ao remetente original da mensagem.

#### Scenario: Resposta automática ao sender
- **WHEN** um agente processa uma mensagem e conclui com `SAC_DONE`
- **THEN** antes de `sac done`, o agente envia o resultado ao `from:` original via `sac send <sender> "<resultado>"`
