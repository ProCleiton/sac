## ADDED Requirements

### Requirement: Comando fan-out
O sistema SHALL expor o comando `sac fanout <template> <targets...>` que dispara o mesmo template simultaneamente para N agentes e coleta as replies.

#### Scenario: Fan-out para múltiplos agentes
- **WHEN** `sac fanout "Revise o codigo em src/" dev-1 auditor secops` é executado
- **THEN** uma mensagem é criada na inbox de cada agente alvo com o mesmo corpo
- **AND** cada mensagem contém cabeçalho `fanout_id: <id>` e `fanout_group: <id_do_grupo>`
- **AND** o evento `fanout` é registrado em `log.jsonl` com contagem de targets

#### Scenario: Fan-out com template vazio
- **WHEN** `sac fanout "" dev-1 auditor` é executado
- **THEN** o sistema rejeita com erro: "template não pode ser vazio"

#### Scenario: Fan-out sem targets
- **WHEN** `sac fanout "mensagem"` é executado sem targets
- **THEN** o sistema rejeita com erro: "pelo menos um target é necessário"

### Requirement: Coleta chaveada de replies
O sistema SHALL coletar as replies dos agentes do fan-out, chaveadas por nome do agente, e entregar um agregado ao solicitante.

#### Scenario: Coleta de todas as replies
- **GIVEN** fan-out para dev-1, auditor, secops
- **WHEN** todos os 3 agentes enviam reply
- **THEN** o daemon coleta as replies em um agregado
- **AND** entrega o agregado ao solicitante como uma única mensagem
- **AND** o agregado contém as replies chaveadas por agente: `{"dev-1": "...", "auditor": "...", "secops": "..."}`

#### Scenario: Coleta parcial (timeout)
- **GIVEN** fan-out com timeout configurado (ex.: `--timeout 300`)
- **WHEN** alguns agentes não respondem dentro do timeout
- **THEN** o agregado inclui as replies recebidas
- **AND** os agentes sem reply são listados como `"<agente>": "TIMEOUT"`
- **AND** o evento `fanout_timeout` é registrado em `log.jsonl`

#### Scenario: Resiliência a crash do daemon
- **GIVEN** um fan-out com coleta parcial persistida em `.sac/fanout/<id>.partial.json`
- **WHEN** o daemon reinicia
- **THEN** o fan-out pendente é retomado com novo timeout
- **AND** as replies já coletadas são preservadas

### Requirement: Timeout configurável no fan-out
O comando `sac fanout` SHALL aceitar flag `--timeout <segundos>` para definir o tempo máximo de espera por replies (default 600s).

#### Scenario: Timeout customizado
- **WHEN** `sac fanout --timeout 120 "template" dev-1 auditor` é executado
- **THEN** o daemon aguarda no máximo 120s pelas replies
- **AND** após o timeout, entrega o agregado parcial

#### Scenario: Timeout default
- **WHEN** `sac fanout "template" dev-1` é executado sem `--timeout`
- **THEN** o daemon usa o timeout default de 600s
