## ADDED Requirements

### Requirement: Flags de budget no comando send
O comando `sac send` SHALL aceitar as flags opcionais `--max-tasks`, `--max-messages` e `--max-wall-time` em conjunto com `--run <id>`, definindo os budgets da run no momento da criação (primeira mensagem com o run_id) e sobrescrevendo os valores do sac.toml.

#### Scenario: send com budgets inline criando run
- **WHEN** `sac send dev-1 "Revise o código" --run r1 --max-tasks 10 --max-wall-time 600` é executado e a run `r1` não existe
- **THEN** a run é criada usando os budgets fornecidos em vez dos valores do sac.toml

#### Scenario: flags de budget sem --run
- **WHEN** `sac send dev-1 "tarefa" --max-tasks 10` é executado sem `--run`
- **THEN** o sistema rejeita com erro: "flags de budget exigem --run"
