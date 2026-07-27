## MODIFIED Requirements

### Requirement: Comando init — questionário interativo
O sistema SHALL expor o comando `sac init` que guia o usuário na criação de
`.sac/sac.toml` e `.sac/prompts/*.md` via input()/print(), sem exigir leitura de
documentação externa: toda pergunta tem hint com exemplo concreto.

#### Scenario: init interativo (TTY)
- **GIVEN** diretório sem `.sac/sac.toml`
- **AND** stdin é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema abre explicando o que será gerado (`.sac/sac.toml`, `.sac/`, `.sac/prompts/*.md`)
- **AND** pergunta: nome da sessão (default "sac", hint com exemplos e onde o nome aparece), socket (hint com exemplo de caminho), boot_wait global (hint com faixa sugerida), número de agentes
- **AND** o agente 1 é anunciado como leader/orquestrador (header + hint do papel) e NÃO recebe pergunta de papel nem de contrato
- **AND** para cada agente 2+: nome, comando (default detectado no PATH — ver Requirement "Detecção de harness no init"), contrato via catálogo (ver Requirement "Catálogo de contratos canônicos"), modelo, boot_wait específico (hint com exemplo)
- **AND** agentes 2+ são `aux` automaticamente (sem pergunta de papel)
- **AND** agrupamento opcional de janelas (ver Requirement "Agrupamento de janelas no init")
- **AND** ao final, gera `.sac/sac.toml` e `.sac/prompts/*.md` com o contrato de cada agente
- **AND** ao final do fluxo, instala automaticamente os plugins canônicos (sem pergunta no wizard; falha de rede gera aviso orientando `sac plugins install`, sem abortar)
- **AND** imprime checklist de próximos passos atualizado com os novos caminhos (sem passo de plugins — é automático)

#### Scenario: init não interativo (sem TTY)
- **GIVEN** stdin não é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema imprime erro: "modo interativo requer terminal — use --config para apontar um sac.toml existente"
- **AND** retorna exit 1

#### Scenario: init com sac.toml existente
- **GIVEN** `.sac/sac.toml` ou `sac.toml` já existe no diretório
- **WHEN** `sac init` é executado
- **THEN** o sistema pergunta se deseja sobrescrever (confirmação)
- **AND** se não, aborta com exit 0

#### Scenario: init valida nomes (charset)
- **GIVEN** usuário digita nome com espaço ou caractere especial
- **WHEN** `sac init` valida o nome
- **THEN** rejeita com "entrada inválida" e repete a pergunta
- **AND** só aceita `[A-Za-z0-9_-]`

#### Scenario: init valida round-trip do TOML gerado
- **GIVEN** todas as respostas coletadas
- **WHEN** o TOML é gerado internamente
- **THEN** o sistema valida o TOML com `tomllib.loads()` antes de escrever
- **AND** se inválido, aborta com erro "TOML gerado é inválido"

#### Scenario: init com prompts existentes
- **GIVEN** diretório `.sac/prompts/` já existe com arquivos .md
- **WHEN** `sac init` vai gerar prompts
- **THEN** pergunta se deseja sobrescrever
- **AND** se não, mantém prompts existentes
