## MODIFIED Requirements

### Requirement: Poke com instrução de reporte imediato
O sistema SHALL incluir no texto do poke do daemon a instrução de que, se o
worker estiver travado ou sem saber como prosseguir, ele deve reportar a
situação imediatamente ao líder. O poke SHALL também instruir que, se a
tarefa já foi concluída, o worker REENVIE o resultado ao líder — mesmo que
já tenha enviado antes, pois a entrega pode ter falhado — antes de concluir
com `sac done`: reenvio duplicado é preferível a trabalho travado.

#### Scenario: Poke instrui reporte ao líder
- **GIVEN** daemon ativo e mensagem claimed stale para um worker
- **WHEN** o daemon envia o poke
- **THEN** o texto contém a instrução de concluir com `sac done <id>`
- **AND** contém "se estiver travado ou sem saber como prosseguir, reporte
  AGORA ao líder" com o comando `sac send <líder> "<situação>"` usando o nome
  real do líder

#### Scenario: Poke instrui reenvio de resultado já enviado
- **GIVEN** daemon ativo e mensagem claimed stale para um worker
- **WHEN** o daemon envia o poke
- **THEN** o texto instrui que, se a tarefa já foi concluída, o worker
  REENVIE o resultado ao líder com `sac send <líder> "..."` usando o nome
  real do líder
- **AND** o texto deixa explícito que o reenvio vale mesmo que o resultado
  já tenha sido enviado antes (a entrega pode ter falhado)
- **AND** a instrução de reenvio precede a de `sac done <id>`
