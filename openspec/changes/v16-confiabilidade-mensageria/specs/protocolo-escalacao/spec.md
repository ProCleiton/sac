## ADDED Requirements

### Requirement: Hierarquia de escalação worker → líder → humano
O sistema SHALL injetar um contrato de escalação em todo prompt de agente
(boot via `sac up` e `sac inject`), independente do prompt_file configurado,
garantindo que workers nunca falem diretamente com o humano e que apenas o
líder se reporte ao humano.

#### Scenario: Worker recebe contrato de escalação no boot
- **GIVEN** um agente com role `aux` e líder `lead-coordinator` no `sac.toml`
- **WHEN** a sessão sobe via `sac up` ou roda-se `sac inject <agente>`
- **THEN** o texto injetado no pane contém o contrato de escalação ANTES do
  conteúdo do prompt_file
- **AND** o contrato informa que o worker NUNCA fala com o humano
- **AND** o contrato instrui: dúvida, erro, bloqueio ou falta de permissão →
  reportar ao líder com `sac send lead-coordinator "<situação>"` e aguardar

#### Scenario: Agente sem prompt_file também recebe o contrato
- **GIVEN** um agente sem `prompt_file` configurado
- **WHEN** roda-se `sac inject <agente>`
- **THEN** o contrato de escalação é injetado mesmo assim

#### Scenario: Líder recebe versão própria do contrato
- **GIVEN** o agente com role `leader`
- **WHEN** o prompt é injetado
- **THEN** o contrato informa que ele é o ÚNICO que fala com o humano
  (`sac send user`)
- **AND** que workers se reportam a ele e os problemas deles são sua
  responsabilidade de triagem

### Requirement: Poke com instrução de reporte imediato
O sistema SHALL incluir no texto do poke do daemon a instrução de que, se o
worker estiver travado ou sem saber como prosseguir, ele deve reportar a
situação imediatamente ao líder.

#### Scenario: Poke instrui reporte ao líder
- **GIVEN** daemon ativo e mensagem claimed stale para um worker
- **WHEN** o daemon envia o poke
- **THEN** o texto contém a instrução de concluir com `sac done <id>`
- **AND** contém "se estiver travado ou sem saber como prosseguir, reporte
  AGORA ao líder" com o comando `sac send <líder> "<situação>"` usando o nome
  real do líder

### Requirement: Daemon escala worker sem progresso ao líder
O sistema SHALL, após `poke_escalate_after` pokes (default 3) em uma mesma
mensagem claimed sem `done`, escalar automaticamente ao líder para que ele
decida a recuperação.

#### Scenario: Escalonamento após N pokes
- **GIVEN** daemon ativo, mensagem claimed stale e `poke_escalate_after = 3`
- **WHEN** o 3º poke é enviado sem que `sac done` tenha ocorrido
- **THEN** o daemon registra evento `escalate` no log (agent, id, pokes)
- **AND** envia mensagem automática ao líder com sender `daemon` relatando
  "worker <w> sem progresso na tarefa <id> após 3 pokes — possível
  travamento", sugerindo inspeção com `sac recv <w>`

#### Scenario: Escala uma única vez por mensagem
- **GIVEN** uma mensagem já escalada
- **WHEN** pokes subsequentes ocorrem para a mesma mensagem
- **THEN** nenhum novo evento `escalate` nem nova mensagem ao líder é gerado
- **AND** os pokes continuam no teto do backoff (600s)
