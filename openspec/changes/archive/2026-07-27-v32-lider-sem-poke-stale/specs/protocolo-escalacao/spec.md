## MODIFIED Requirements

### Requirement: Daemon escala worker sem progresso ao líder
O sistema SHALL, após `poke_escalate_after` pokes (default 3) em uma mesma
mensagem claimed sem `done`, escalar automaticamente ao líder para que ele
decida a recuperação. A escalação SHALL NOT ocorrer para o próprio líder:
ele é o topo da hierarquia de agentes e o humano já acompanha o seu pane —
auto-escalação seria ruído na inbox dele.

#### Scenario: Escalonamento após N pokes
- **GIVEN** daemon ativo, mensagem claimed stale e `poke_escalate_after = 3`
- **WHEN** o 3º poke é enviado sem que `sac done` tenha ocorrido
- **THEN** o daemon registra evento `escalate` no log (agent, id, pokes)
- **AND** envia mensagem automática ao líder com sender `daemon` relatando
  "worker <w> sem progresso na tarefa <id> após 3 pokes — possível
  travamento", sugerindo inspeção com `sac recv <w>`

#### Scenario: Líder nunca é auto-escalado
- **GIVEN** o líder com mensagem claimed sem `done`
- **WHEN** o daemon varre os agentes por qualquer número de ciclos
- **THEN** nenhuma mensagem de escalação é enviada ao líder sobre ele mesmo
- **AND** nenhum evento `escalate` é registrado com o líder como agente

#### Scenario: Escala uma única vez por mensagem
- **GIVEN** uma mensagem já escalada
- **WHEN** pokes subsequentes ocorrem para a mesma mensagem
- **THEN** nenhum novo evento `escalate` nem nova mensagem ao líder é gerado
- **AND** os pokes continuam no teto do backoff (600s)
