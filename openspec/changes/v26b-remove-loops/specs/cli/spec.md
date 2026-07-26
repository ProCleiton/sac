## REMOVED Requirements

### Requirement: Execução de loops declarados
**Reason**: Loops declarados removidos (v26b) junto com o comando `sac run` —
a delegação e os ciclos de revisão passam a ser disciplina do contrato do
líder, não mecanismo do daemon.
**Migration**: remova `[[loops]]` do config e expresse o ciclo no contrato do
líder (delegar com `sac send`, cobrar revisão, iterar até convergir).

## MODIFIED Requirements

### Requirement: Comando init — questionário interativo
O sistema SHALL expor o comando `sac init` que guia o usuário na criação de
`.sac/sac.toml` e `prompts/*.md` via input()/print(), sem exigir leitura de
documentação externa: toda pergunta tem hint com exemplo concreto.

#### Scenario: init interativo (TTY)
- **GIVEN** diretório sem `.sac/sac.toml`
- **AND** stdin é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema abre explicando o que será gerado (`.sac/sac.toml`, `.sac/`, `prompts/*.md`)
- **AND** pergunta: nome da sessão (default "sac", hint com exemplos e onde o nome aparece), socket (hint com exemplo de caminho), boot_wait global (hint com faixa sugerida), número de agentes
- **AND** o agente 1 é anunciado como leader/orquestrador (header + hint do papel) e NÃO recebe pergunta de papel nem de contrato
- **AND** para cada agente 2+: nome, comando (default detectado no PATH — ver Requirement "Detecção de harness no init"), contrato via catálogo (ver Requirement "Catálogo de contratos canônicos"), modelo, boot_wait específico (hint com exemplo)
- **AND** agentes 2+ são `aux` automaticamente (sem pergunta de papel)
- **AND** agrupamento opcional de janelas (ver Requirement "Agrupamento de janelas no init")
- **AND** ao final, gera `.sac/sac.toml` e `prompts/*.md` com o contrato de cada agente
- **AND** imprime checklist de próximos passos atualizado com os novos caminhos

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
- **GIVEN** diretório `prompts/` já existe com arquivos .md
- **WHEN** `sac init` vai gerar prompts
- **THEN** pergunta se deseja sobrescrever
- **AND** se não, mantém prompts existentes

### Requirement: Comando doctor — diagnóstico do ambiente

O sistema SHALL expor o comando `sac doctor` que verifica os pré-requisitos do
ambiente e reporta OK/FALHA por item com orientação de correção. O comando é
read-only (sem side-effects). Exit 0 se todos os itens essenciais estão OK;
exit 1 se algum item essencial falhar. Itens não essenciais (warning) não
alteram o exit code.

#### Checklist de verificação

| Item | Essencial | Critério |
|------|-----------|----------|
| Python version | sim | >= 3.11 |
| tmux presence | sim | `shutil.which("tmux")` não nulo |
| tmux version | sim | `tmux -V` retorna versão >= 3.2 (o layout grid exige) |
| Socket dir writable | sim | se `socket` configurado, diretório-pai existe e é gravável |
| Config loads | sim | config resolvido pela cadeia de descoberta é parseável sem erro; saída indica qual arquivo foi usado |
| Harnesses in PATH | não | cada `command` dos agentes em `[[agents]]` existe no PATH (warning individual) |
| Legado ignorado | não | `./sac.toml` existe na raiz (warning: fallback removido — mover para `.sac/` ou apagar) |
| openspec CLI | não | `shutil.which("openspec")` não nulo (warning com orientação de instalação — stack canônica) |

#### Formato de saída

```
[OK]  Python 3.12.5
[OK]  tmux 3.4
[OK]  openspec found in PATH
[OK]  socket dir ~/.sac-esteira is writable
[OK]  config loads (.sac/sac.toml, 3 agents)
[WARN] harness 'kimi' not found in PATH (config may be for another machine)
[WARN] ./sac.toml existe na raiz mas é ignorado (fallback removido) — mova para .sac/ ou apague
```

Itens essenciais com FALHA usam `[FAIL]` e incluem orientação de correção:

```
[FAIL] tmux not found — install with: apt install tmux / brew install tmux
[FAIL] Python 3.10.2 < 3.11 — upgrade Python to 3.11+
```

#### Scenario: doctor — tudo OK

- **GIVEN** ambiente com Python >= 3.11, tmux >= 3.2, socket válido, config
  válida, todos os harnesses no PATH
- **WHEN** `sac doctor` é executado
- **THEN** todos os itens reportam `[OK]`
- **AND** exit code é 0

#### Scenario: doctor — tmux ausente (essencial)

- **GIVEN** `shutil.which("tmux")` retorna None
- **WHEN** `sac doctor` é executado
- **THEN** o item tmux reporta `[FAIL]` com orientação de instalação
- **AND** exit code é 1

#### Scenario: doctor — Python version insuficiente

- **GIVEN** `sys.version_info < (3, 11)`
- **WHEN** `sac doctor` é executado
- **THEN** o item Python reporta `[FAIL]` com upgrade instructions
- **AND** exit code é 1

#### Scenario: doctor — harness ausente (não essencial)

- **GIVEN** config com `command = "kimi"` e `shutil.which("kimi")` é None
- **WHEN** `sac doctor` é executado
- **THEN** o item do harness reporta `[WARN]` (não `[FAIL]`)
- **AND** exit code permanece 0 (outros itens essenciais OK)

#### Scenario: doctor — sem config (não essencial)

- **GIVEN** diretório sem config em nenhum caminho da cadeia e sem `$SAC_CONFIG`
- **WHEN** `sac doctor` é executado
- **THEN** itens independentes de config (Python, tmux) rodam normalmente
- **AND** o item config reporta `[WARN]` (config não encontrada, ignorando
  checagens dependentes)
- **AND** se `./sac.toml` existir na raiz, o aviso inclui orientação de migração
- **AND** items dependentes de config (socket, harnesses) são pulados/silenciados
- **AND** exit code é 0

#### Scenario: doctor — config ambíguo (não essencial)

- **GIVEN** `./.sac/sac.toml` e `./sac.toml` existem no diretório
- **WHEN** `sac doctor` é executado
- **THEN** o item config indica qual arquivo foi usado (`.sac/sac.toml`)
- **AND** um `[WARN]` informa que o `./sac.toml` da raiz é ignorado (fallback
  removido) e orienta mover para `.sac/` ou apagar

#### Scenario: doctor — openspec ausente (não essencial)

- **GIVEN** `shutil.which("openspec")` retorna None
- **WHEN** `sac doctor` é executado
- **THEN** o item openspec reporta `[WARN]` com orientação de instalação
- **AND** exit code permanece 0

#### Scenario: doctor — tmux version < 3.2

- **GIVEN** `tmux -V` retorna "tmux 3.1"
- **WHEN** `sac doctor` é executado
- **THEN** o item tmux version reporta `[FAIL]` com upgrade instructions
- **AND** exit code é 1

#### Scenario: doctor — sem side-effects

- **WHEN** `sac doctor` é executado
- **THEN** nenhum arquivo é criado, modificado ou removido
- **AND** nenhum processo tmux é iniciado ou terminado
- **AND** nenhum dado de mensageria é alterado

### Requirement: Sidebar informativa
O sistema SHALL exibir um painel lateral com o estado atual dos agentes.

#### Scenario: sidebar — painel de estado
- **WHEN** `sac sidebar` é executado
- **THEN** o sistema renderiza: agentes com marcadores de estado (idle, inbox, working) e atalhos C-b <N>
- **AND** é usado internamente nos panes de sidebar de cada janela (loop `clear; sac sidebar; sleep 5`)

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
editável pelo usuário depois do init.

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
