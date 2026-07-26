# Delta: cli

## ADDED Requirements

### Requirement: Resolução de config via env da sessão
O sistema SHALL usar o valor da variável de ambiente `SAC_CONFIG` como default do parâmetro `--config`, para que comandos `sac` executados dentro de panes de agente resolvam a configuração da sessão correta independente do cwd.

#### Scenario: SAC_CONFIG definido
- **WHEN** `sac <comando>` é executado sem `--config` e a env `SAC_CONFIG` está definida
- **THEN** a configuração é carregada do caminho em `SAC_CONFIG`, mesmo que o cwd não contenha `sac.toml` (ou contenha outro)

#### Scenario: SAC_CONFIG ausente
- **WHEN** `sac <comando>` é executado sem `--config` e sem `SAC_CONFIG` no ambiente
- **THEN** a configuração é carregada de `./sac.toml` (comportamento atual)

#### Scenario: --config explícito tem precedência
- **WHEN** `sac --config /caminho/x.toml <comando>` é executado com `SAC_CONFIG` definido
- **THEN** a configuração é carregada de `/caminho/x.toml`
