# layout-grid Specification

## Purpose
TBD - created by archiving change v17-layout-ccb. Update Purpose after archive.
## Requirements
### Requirement: Gramática de layout [windows]
O sistema SHALL aceitar specs de layout na forma `;` (split horizontal —
colunas lado a lado) e `,` (split vertical — empilhado), onde cada folha é o
nome de um agente, com `,` ligando mais forte que `;`.

#### Scenario: Spec com uma coluna empilhada
- **GIVEN** o spec `"dev-1,auditor"`
- **WHEN** o parser processa
- **THEN** o resultado é um nó vertical (empilhado) com folhas dev-1 e auditor

#### Scenario: Spec com duas colunas
- **GIVEN** o spec `"dev-1;auditor"`
- **WHEN** o parser processa
- **THEN** o resultado é um nó horizontal (colunas) com folhas dev-1 e auditor

#### Scenario: Precedência de vírgula sobre ponto-e-vírgula
- **GIVEN** o spec `"dev-1,auditor;info"`
- **WHEN** o parser processa
- **THEN** a coluna 1 contém dev-1 sobre auditor e a coluna 2 contém info

#### Scenario: Spec vazio ou folha vazia rejeitado
- **GIVEN** o spec `""` ou `"dev-1,,auditor"` ou `"dev-1;"`
- **WHEN** o parser processa
- **THEN** o sistema rejeita com ConfigError

### Requirement: Plano de layout com percentuais proporcionais
O sistema SHALL transformar a árvore de splits em um plano de panes com
percentuais proporcionais ao número de folhas de cada nó, aplicados ao espaço
restante (regra equivalente à do CCB).

#### Scenario: Duas folhas empilhadas dividem 50/50
- **GIVEN** o spec `"dev-1,auditor"`
- **WHEN** o plano é construído
- **THEN** dev-1 ocupa 50% superior e auditor 50% inferior

#### Scenario: Colunas desbalanceadas por folhas
- **GIVEN** o spec `"dev-1,auditor;info"`
- **WHEN** o plano é construído
- **THEN** a coluna 1 (2 folhas) ocupa ~67% da largura dos agentes e a
  coluna 2 (1 folha) ~33%

### Requirement: Materialização do grid no boot
O sistema SHALL, quando `[windows]` estiver presente, criar cada window com
uma sidebar à esquerda (15% da largura, mínimo 28 colunas) e os panes de
agentes conforme o plano, usando os wrappers tmux existentes.

#### Scenario: Boot com grid 2x1
- **GIVEN** `[windows]` com `main = "leader"` e `trabalho = "dev-1,auditor"`
- **WHEN** `sac up` executa
- **THEN** a window `trabalho` tem sidebar à esquerda + dev-1 sobre auditor
- **AND** cada pane de harness recebe `SAC_AGENT` e título do agente
- **AND** a window `dash` (daemon + log) é criada por último
- **AND** o select final cai na primeira window declarada (`main`)

#### Scenario: Boot sem [windows] preserva layout legado
- **GIVEN** config sem seção `[windows]`
- **WHEN** `sac up` executa
- **THEN** o layout atual (1 window por agente + dash, select no leader) é
  reproduzido sem alteração

### Requirement: Sidebar global com tree, comms e tips
O sistema SHALL renderizar no `sac sidebar` três seções: árvore de windows e
agentes com indicadores, últimos eventos de mensageria e atalhos tmux.

#### Scenario: Tree com indicadores de atividade
- **WHEN** a sidebar renderiza
- **THEN** a window ativa aparece com `>`; cada agente com `●` (claimed),
  `!` (escalado pelo daemon), `◐` (inbox pendente) ou `·` (ocioso), mais o
  provider entre colchetes; o agente focado recebe `*`

#### Scenario: Comms com últimos eventos
- **GIVEN** log.jsonl com eventos recentes
- **WHEN** a sidebar renderiza
- **THEN** os últimos 5 eventos aparecem como `HH:MM sender→to evento`

#### Scenario: Tips com atalhos fixos
- **WHEN** a sidebar renderiza
- **THEN** a seção tips lista os atalhos tmux (navegação de pane, resize,
  zoom, tree, copy-mode)

### Requirement: Toggle e identidade da sidebar
O sistema SHALL marcar o pane da sidebar com a pane option
`@pane_role=sidebar` e SHALL oferecer toggle da sidebar na window corrente
(`sac sidebar --toggle` + bind `prefix + e`), criando o pane com split à
esquerda quando ausente e matando-o quando presente.

#### Scenario: Toggle cria sidebar ausente
- **GIVEN** uma window sem pane `@pane_role=sidebar`
- **WHEN** roda-se `sac sidebar --toggle` (ou `prefix + e`)
- **THEN** um split à esquerda (15%, piso 28 col) é criado rodando a sidebar
- **AND** o pane é marcado com `@pane_role=sidebar`
- **AND** o foco volta ao pane original

#### Scenario: Toggle remove sidebar presente
- **GIVEN** uma window com pane `@pane_role=sidebar`
- **WHEN** roda-se `sac sidebar --toggle`
- **THEN** o pane da sidebar é morto

#### Scenario: Bind prefix+e configurado no up
- **WHEN** `sac up` executa
- **THEN** a sessão tem bind `e` para `sac sidebar --toggle` na window
  corrente

### Requirement: Bordas de pane com label e cor estável por agente
O sistema SHALL exibir `pane-border-status top` com o nome do agente e
aplicar uma cor estável derivada de hash do nome (paleta fixa), com realce
no pane ativo.

#### Scenario: Cor estável entre boots
- **GIVEN** o agente `dev-1`
- **WHEN** a cor é calculada duas vezes (boots diferentes)
- **THEN** o valor é idêntico (hash do nome na paleta)

#### Scenario: Pane ativo realçado
- **WHEN** o foco muda de pane (hook after-select-pane)
- **THEN** o pane ativo recebe borda na cor do agente com linha heavy e os
  demais ficam em cinza

### Requirement: Status bar com modo, git e agente focado
O sistema SHALL configurar a status line da sessão com: à esquerda, segmento
de modo (prefix/copy) e branch git do projeto; à direita, agente do pane
ativo, versão do SAC e data/hora.

#### Scenario: Status bar configurada no up
- **WHEN** `sac up` executa
- **THEN** a status line mostra o modo e o branch git à esquerda
- **AND** mostra o título do pane ativo (agente), `SAC <versão>` e data à
  direita
- **AND** `window-status-format` fica vazio (a tree da sidebar substitui a
  lista de windows)

