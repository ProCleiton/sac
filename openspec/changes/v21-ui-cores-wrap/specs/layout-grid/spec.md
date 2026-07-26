## MODIFIED Requirements

> **Nota:** Esta change MODIFICA quatro pontos no spec master `layout-grid`: (1) padding das caixas comms/tips (23), (2) truncamento (NÃO wrap) em `_render_sidebar`, (3) sidebar tree sem modelo AI (só harness), (4) SIDEBAR_PCT 15→18 com piso 28. Remove a requirement de wrap da proposta original. Após archive, o spec master refletirá estas alterações.

### Requirement: Sidebar tree — sem modelo AI (apenas harness)

A árvore de agentes na sidebar SHALL mostrar o harness (basename do command, ex.: `kimi`) como metadado do agente, mas NÃO o modelo (`--model`, ex.: `k3`, `v4`). O modelo é escolha do humano no harness — o SAC não o exibe, preservando agnosticidade. A requirement "modelo por agente" do spec master (v20) fica MODIFIED.

#### Scenario: Árvore mostra harness, não modelo AI
- **GIVEN** agente com `command = "kimi"` e `args = ["--model", "k3"]`
- **WHEN** a sidebar renderiza a linha do agente
- **THEN** a linha contém o basename `kimi` (do `command`) em cinza
- **AND** NÃO contém `k3` nem qualquer referência ao `--model`

### Requirement: Caixas comms/tips com padding fixo 23

A função `_section()` SHALL usar padding `23` (constante fixa, não range). O piso da sidebar é `SIDEBAR_MIN_COLS=28`, garantindo que o box header caiba com margem.

#### Scenario: Box comms/tips com padding 23
- **GIVEN** sidebar com qualquer largura >= 28 colunas
- **WHEN** `_section("comms")` ou `_section("tips")` é chamado
- **THEN** a linha renderizada tem padding `23` (ex.: `╭─ comms ───────────────────╮`)
- **AND** a linha nunca ultrapassa a largura da sidebar

### Requirement: Truncamento automático na sidebar (NÃO wrap — substitui requirement de wrap da proposta original)

O `_render_sidebar` SHALL usar truncamento (`_truncate_ansi`), NÃO wrapping. Linhas que excedem a largura do terminal SHALL ser cortadas com reset ANSI ao final — sem quebra de linha. A requirement de wrap da proposta original fica REMOVED com a presente reescrita como truncamento.

#### Scenario: Linha longa é truncada
- **GIVEN** linha de árvore ou conteúdo que excede a largura do terminal
- **WHEN** a sidebar renderiza
- **THEN** a linha é cortada na largura visível
- **AND** códigos ANSI são preservados até o corte
- **AND** o terminador `\033[0m` é inserido ao final

#### Scenario: Linhas curtas não são afetadas
- **GIVEN** linha que cabe dentro da largura do terminal
- **WHEN** a sidebar renderiza
- **THEN** a linha não é truncada (comportamento igual ao atual)

### Requirement: Tips — um atalho por linha, sem scrollbar

A seção tips SHALL exibir um atalho por linha com indentação de 2 espaços (igual à seção comms). NÃO deve ter barra de rolagem (scrollbar/trilho/polegar) — o usuário reprovou visualmente durante homologação.

#### Scenario: Tips sem scrollbar
- **GIVEN** seção tips com `TIPS_LINES` contendo 8 atalhos
- **WHEN** a sidebar renderiza
- **THEN** cada atalho aparece em linha própria com prefixo `  ` (2 espaços)
- **AND** NÃO há trilho, polegar ou qualquer elemento de scrollbar

### Requirement: Largura da sidebar — SIDEBAR_PCT 18% com piso 28

A largura da sidebar SHALL ser calculada como 18% da largura da janela (SIDEBAR_PCT=18), com piso mínimo de `SIDEBAR_MIN_COLS=28` colunas. O hook `client-resized` usa o mesmo percentual. O layout legado (dash) mantém largura fixa de 30 colunas.

#### Scenario: Sidebar grid — 18% com piso 28
- **GIVEN** janela de 200 colunas
- **WHEN** a sidebar é criada no grid
- **THEN** a largura calculada é `max(28, round(200 * 18 / 100))` = 36 colunas
- **AND** o hook `client-resized` recalcula com a mesma fórmula

#### Scenario: Sidebar grid — piso 28
- **GIVEN** janela de 100 colunas
- **WHEN** a sidebar é criada no grid
- **THEN** `100 * 18 / 100` = 18 → aplica piso: 28 colunas
- **AND** o hook `client-resized` também respeita o piso

#### Scenario: Layout legado (dash) — largura fixa 30
- **GIVEN** `_materialize_dash`
- **WHEN** a sidebar é criada
- **THEN** a largura fixa é 30 (SIDEBAR_WIDTH)
- **AND** independe de SIDEBAR_PCT e SIDEBAR_MIN_COLS
