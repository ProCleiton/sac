## MODIFIED Requirements

### Requirement: Resolução de config via env da sessão
O sistema SHALL resolver o caminho do config pela ordem de precedência:
`--config` (flag explícita) > `$SAC_CONFIG` > `./.sac/sac.toml` > `./sac.toml`
(fallback legado). A env `SAC_CONFIG` permite que comandos `sac` executados
dentro de panes de agente resolvam a configuração da sessão correta
independente do cwd; `sac up` SHALL exportar `SAC_CONFIG` com o caminho
efetivamente usado.

#### Scenario: SAC_CONFIG definido
- **WHEN** `sac <comando>` é executado sem `--config` e a env `SAC_CONFIG` está definida
- **THEN** a configuração é carregada do caminho em `SAC_CONFIG`, mesmo que o cwd não contenha config (ou contenha outro)

#### Scenario: SAC_CONFIG ausente
- **WHEN** `sac <comando>` é executado sem `--config` e sem `SAC_CONFIG` no ambiente
- **THEN** a configuração é resolvida pela cadeia de diretórios: `./.sac/sac.toml`, depois `./sac.toml` (fallback legado)

#### Scenario: Config oculto é preferido ao legado
- **WHEN** `./.sac/sac.toml` e `./sac.toml` existem e não há `--config` nem `SAC_CONFIG`
- **THEN** a configuração é carregada de `./.sac/sac.toml`

#### Scenario: Fallback legado
- **WHEN** apenas `./sac.toml` existe e não há `--config` nem `SAC_CONFIG`
- **THEN** a configuração é carregada de `./sac.toml` (esteiras antigas não quebram)

#### Scenario: --config explícito tem precedência
- **WHEN** `sac --config /caminho/x.toml <comando>` é executado com `SAC_CONFIG` definido
- **THEN** a configuração é carregada de `/caminho/x.toml`

#### Scenario: Nenhum config encontrado
- **WHEN** nenhum dos caminhos da cadeia existe
- **THEN** o sistema imprime erro indicando os caminhos tentados e sugere `sac init`
- **AND** retorna exit 1

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
- **AND** loops opcionais (nome, sequência de agentes, max_iterations)
- **AND** agrupamento opcional de janelas (ver Requirement "Agrupamento de janelas no init")
- **AND** ao final, gera `.sac/sac.toml` e `prompts/*.md` com o contrato de cada agente
- **AND** imprime checklist de próximos passos atualizado com os novos caminhos

#### Scenario: init não interativo (sem TTY)
- **GIVEN** stdin não é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema imprime erro: "modo interativo requer terminal — use --config para apontar um sac.toml existente"
- **AND** retorna exit 1

#### Scenario: init com config existente
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
| Config ambiguity | não | `./.sac/sac.toml` e `./sac.toml` coexistem (warning; o `.sac/` vence) |
| openspec CLI | não | `shutil.which("openspec")` não nulo (warning com orientação de instalação — stack canônica) |

#### Formato de saída

```
[OK]  Python 3.12.5
[OK]  tmux 3.4
[OK]  socket dir ~/.sac-esteira is writable
[OK]  config loads (.sac/sac.toml, 3 agents, 1 loop)
[WARN] harness 'kimi' not found in PATH (config may be for another machine)
[WARN] openspec not found in PATH — stack canônica: npm i -g @fission-ai/openspec (ou equivalente)
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
- **AND** items dependentes de config (socket, harnesses) são pulados/silenciados
- **AND** exit code é 0

#### Scenario: doctor — config ambíguo (não essencial)

- **GIVEN** `./.sac/sac.toml` e `./sac.toml` existem no diretório
- **WHEN** `sac doctor` é executado
- **THEN** o item config indica qual arquivo foi usado (`.sac/sac.toml`)
- **AND** um `[WARN]` de ambiguidade é exibido

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

## ADDED Requirements

### Requirement: Detecção de harness no init
O sistema SHALL detectar harnesses instalados no PATH durante o `sac init` e
oferecer o primeiro encontrado como default da pergunta de comando, na ordem
de preferência: `kimi` → `opencode` → `claude`. Se nenhum for encontrado, o
default é o placeholder fixo ("kimi" para o agente 1, "opencode" para os
demais). A validação com warning da v22 (comando ausente → corrigir ou
seguir) é mantida para qualquer resposta.

#### Scenario: harness detectado vira default
- **GIVEN** `shutil.which("kimi")` retorna um caminho
- **WHEN** o wizard pergunta o comando de um agente
- **THEN** o default exibido é `kimi` e o hint indica "detectado no seu PATH"

#### Scenario: preferência da ordem canônica
- **GIVEN** `opencode` e `claude` no PATH, `kimi` ausente
- **WHEN** o wizard pergunta o comando
- **THEN** o default exibido é `opencode`

#### Scenario: nenhum harness detectado
- **GIVEN** nenhum dos harnesses canônicos no PATH
- **WHEN** o wizard pergunta o comando
- **THEN** o default é o placeholder fixo e nenhum hint de detecção é exibido

### Requirement: Catálogo de contratos canônicos
O sistema SHALL embutir um catálogo de contratos de papel (dados, em módulo
próprio) usado pelo `sac init`: líder/orquestrador, desenvolvedor, revisor de
código, documentação, deploy/release, segurança e auxiliar genérico. Todo
contrato inclui o protocolo de mensageria SAC (inbox/`sac next`/reply/
`sac done`) mais a disciplina do papel, em texto puro que NÃO exige plugin ou
CLI externo instalado. O agente 1 recebe o contrato de líder sem pergunta;
agentes 2+ escolhem em lista numerada (default: desenvolvedor). O contrato
gerado em `prompts/<nome>.md` é editável pelo usuário depois do init.

#### Scenario: agente 1 recebe contrato de líder sem pergunta
- **GIVEN** o wizard configurando o agente 1
- **WHEN** o init gera os prompts
- **THEN** `prompts/<nome>.md` do agente 1 contém o contrato de líder/orquestrador
- **AND** nenhuma pergunta de catálogo foi feita para o agente 1

#### Scenario: catálogo numerado para agentes aux
- **GIVEN** o wizard configurando o agente 2
- **WHEN** a pergunta de contrato é exibida
- **THEN** a lista numerada de papéis aparece com default "desenvolvedor"
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

### Requirement: Agrupamento de janelas no init
O sistema SHALL perguntar ao final do questionário se o usuário deseja
agrupar agentes em janelas `[windows]` (default: não). Se sim, o wizard coleta
por janela: nome (validado), agentes (nomes separados por espaço, validados
contra os agentes criados) e disposição (`;` lado a lado ou `,` empilhados),
exibindo preview do resultado parcial antes de perguntar se deseja adicionar
outra janela. Agentes fora de qualquer janela mantêm janela própria.

#### Scenario: resposta "não" não gera [windows]
- **GIVEN** o usuário responde "n" ao agrupamento
- **WHEN** o config é gerado
- **THEN** o TOML não contém seção `[windows]`

#### Scenario: janela lado a lado
- **GIVEN** agentes `dev-1` e `dev-2` criados
- **WHEN** o usuário define a janela `dev` com "dev-1 dev-2" e disposição lado a lado
- **THEN** o TOML contém `[windows]` com `dev = "dev-1;dev-2"`

#### Scenario: agente desconhecido é rejeitado
- **GIVEN** o usuário digita um nome de agente inexistente na janela
- **WHEN** o wizard valida
- **THEN** rejeita com mensagem indicando os nomes válidos e repete a pergunta

#### Scenario: agentes fora de janelas mantêm janela própria
- **GIVEN** 3 agentes criados e apenas 2 agrupados em uma janela
- **WHEN** o config é gerado
- **THEN** o agente não agrupado continua com janela própria (comportamento default)

### Requirement: Comando uninstall — remoção segura da configuração
O sistema SHALL expor o comando `sac uninstall` que remove a configuração do
SAC no workspace atual de forma segura e confirmada: `.sac/` (config e
estado), `prompts/` e o `sac.toml` legado da raiz, se existir. O comando
recusa se a sessão tmux do config estiver no ar e exige confirmação digitando
o nome da sessão. Nada fora do diretório do workspace é removido.

#### Scenario: sessão no ar — recusa
- **GIVEN** a sessão tmux definida no config está ativa
- **WHEN** `sac uninstall` é executado
- **THEN** o sistema recusa com mensagem orientando `sac down` antes
- **AND** nada é removido
- **AND** retorna exit 1

#### Scenario: confirmação incorreta aborta
- **GIVEN** a sessão não está no ar
- **WHEN** o usuário digita algo diferente do nome da sessão na confirmação
- **THEN** o sistema aborta sem remover nada
- **AND** retorna exit 0

#### Scenario: confirmação correta remove
- **GIVEN** a sessão não está no ar e o usuário digita o nome da sessão
- **WHEN** `sac uninstall` é executado
- **THEN** o sistema lista o que será removido antes da confirmação
- **AND** remove `.sac/`, `prompts/` e `sac.toml` legado (se existir)
- **AND** nenhum arquivo fora do workspace é tocado
- **AND** retorna exit 0

#### Scenario: nada configurado
- **GIVEN** diretório sem `.sac/`, sem `prompts/` e sem `sac.toml`
- **WHEN** `sac uninstall` é executado
- **THEN** o sistema informa que não há nada para remover
- **AND** retorna exit 0
