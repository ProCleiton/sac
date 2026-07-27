## MODIFIED Requirements

### Requirement: Catálogo de contratos canônicos
O sistema SHALL embutir um catálogo de contratos de papel (dados, em módulo
próprio) usado pelo `sac init`: líder/orquestrador, desenvolvedor, revisor de
código, documentação, deploy/release, segurança e auxiliar genérico. Todo
contrato inclui o protocolo de mensageria SAC (inbox/`sac next`/reply/
`sac done`) mais a disciplina do papel, em texto puro que NÃO exige plugin ou
CLI externo instalado. O contrato de líder SHALL incluir disciplina de
delegação e ciclo de revisão: decompor e delegar com `sac send`, cobrar
revisão do trabalho dos auxiliares, iterar até convergir e escalar ao usuário
só em bloqueio real (substitui os loops declarados, removidos na v26b). O
agente 1 recebe o contrato de líder sem pergunta; agentes 2+ escolhem em lista
numerada que EXCLUI o papel de líder (só pode haver um líder — o agente 1),
com default "desenvolvedor". O contrato gerado em `prompts/<nome>.md` é
editável pelo usuário depois do init. Todo contrato SHALL instruir que arquivos auto-carregados pelo harness (AGENTS.md, CLAUDE.md, regras-comuns.md) são contexto de PROJETO: workflow e memória seguem o contrato SAC e o `sac memory` — não ler pendencias.md nem executar rituais de sessão direta.

#### Scenario: agente 1 recebe contrato de líder sem pergunta
- **GIVEN** o wizard configurando o agente 1
- **WHEN** o init gera os prompts
- **THEN** `prompts/<nome>.md` do agente 1 contém o contrato de líder/orquestrador
- **AND** contém a disciplina de delegação e ciclo de revisão
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
