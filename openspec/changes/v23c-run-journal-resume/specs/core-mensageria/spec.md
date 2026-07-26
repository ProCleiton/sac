## ADDED Requirements

### Requirement: Campo run no cabeçalho da mensagem
O sistema SHALL suportar o campo opcional `run` no cabeçalho do arquivo .msg, associando a mensagem a uma run (agrupador nomeado).

#### Scenario: Cabeçalho com run
- **WHEN** uma mensagem é criada com `sac send ... --run <id>`
- **THEN** o arquivo .msg contém `run: <id>` no cabeçalho
- **AND** o header parsing aceita o campo sem quebrar mensagens existentes (ausente = sem run)

#### Scenario: Conclusão registra checkpoint na run
- **GIVEN** uma mensagem com `run: <id>` no cabeçalho
- **WHEN** ela é concluída via `sac done`
- **THEN** após o move para `done/`, o journal da run registra `task_done` com fsync
- **AND** se o journal não puder ser escrito, o erro é registrado em `log.jsonl` sem desfazer a conclusão
