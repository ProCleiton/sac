## ADDED Requirements

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
