## MODIFIED Requirements

### Requirement: Catálogo de contratos canônicos
O sistema SHALL embutir um catálogo de contratos de papel (dados, em módulo
próprio) usado pelo `sac init`: líder/orquestrador, desenvolvedor, revisor de
código, documentação, deploy/release, segurança e auxiliar genérico. Todo
contrato inclui o protocolo de mensageria SAC (inbox/`sac next`/reply/
`sac done`) mais a disciplina do papel, em texto puro que NÃO exige plugin ou
CLI externo instalado. O agente 1 recebe o contrato de líder sem pergunta;
agentes 2+ escolhem em lista numerada que EXCLUI o papel de líder (só pode
haver um líder — o agente 1), com default "desenvolvedor". O contrato gerado
em `prompts/<nome>.md` é editável pelo usuário depois do init.

#### Scenario: agente 1 recebe contrato de líder sem pergunta
- **GIVEN** o wizard configurando o agente 1
- **WHEN** o init gera os prompts
- **THEN** `prompts/<nome>.md` do agente 1 contém o contrato de líder/orquestrador
- **AND** nenhuma pergunta de catálogo foi feita para o agente 1

#### Scenario: catálogo numerado para agentes aux
- **GIVEN** o wizard configurando o agente 2
- **WHEN** a pergunta de contrato é exibida
- **THEN** a lista numerada NÃO contém "líder/orquestrador"
- **AND** aparece com default "desenvolvedor"
- **AND** Enter seleciona o default

#### Scenario: escolha inválida repete a pergunta
- **GIVEN** o usuário digita um número fora da lista ou texto inválido
- **WHEN** o wizard valida a escolha
- **THEN** rejeita e repete a pergunta

#### Scenario: contrato contém mensageria + disciplina
- **GIVEN** o usuário escolheu "revisor de código" para o agente 2
- **WHEN** o init gera `prompts/<nome>.md`
- **THEN** o arquivo contém o protocolo de mensageria SAC e a disciplina de
  revisão por evidência (bloqueantes vs. warnings)
- **AND** não contém dependência de plugin ou CLI externo para ser seguido

## ADDED Requirements

### Requirement: Sugestão de modelos por harness no init
Na pergunta "Modelo" do `sac init`, o sistema SHALL tentar listar os modelos
válidos do harness escolhido: para `kimi`, os aliases das tabelas
`[models."<alias>"]` de `~/.kimi-code/config.toml` (via tomllib — apenas nomes
de tabelas); para `opencode`, a saída de `opencode models` (com timeout
curto). Se a listagem falhar ou o harness for desconhecido, a pergunta cai no
modo texto livre. Com lista disponível, a resposta é o número do modelo ou
Enter (vazio = não passar `--model`).

#### Scenario: kimi lista aliases do config do usuário
- **GIVEN** o harness escolhido é `kimi` e `~/.kimi-code/config.toml` contém
  tabelas `[models."kimi-code/k3"]` e `[models."esteira/k3"]`
- **WHEN** a pergunta de modelo é exibida
- **THEN** a lista numerada contém `kimi-code/k3` e `esteira/k3`

#### Scenario: opencode lista modelos ao vivo
- **GIVEN** o harness escolhido é `opencode` e `opencode models` retorna
  linhas `opencode/big-pickle`, `opencode/claude-opus-5`
- **WHEN** a pergunta de modelo é exibida
- **THEN** a lista numerada contém esses modelos

#### Scenario: resposta por número
- **GIVEN** a lista de modelos exibida
- **WHEN** o usuário responde um número válido da lista
- **THEN** o modelo correspondente é usado (args `--model <modelo>`)
- **AND** número fora da lista repete a pergunta

#### Scenario: Enter não passa --model
- **GIVEN** a lista de modelos exibida
- **WHEN** o usuário responde vazio
- **THEN** o agente é configurado sem `--model` (default do harness)

#### Scenario: fallback para texto livre
- **GIVEN** harness desconhecido ou falha na listagem (arquivo ausente,
  timeout, erro de parse)
- **WHEN** a pergunta de modelo é exibida
- **THEN** nenhuma lista é mostrada e a resposta é texto livre (comportamento
  anterior), sem erro para o usuário
