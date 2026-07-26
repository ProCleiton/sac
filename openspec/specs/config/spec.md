# Config

## Purpose
Arquivo de configuração `sac.toml` no formato TOML usando `tomllib` da stdlib Python (3.11+). Define a sessão tmux, os agentes participantes e os loops de trabalho declarados. As mesmas configurações de temporização (`notify_interval`, `poke_stale_after`) são usadas pelo daemon de mensageria. Validações: nomes únicos, exatamente um leader, referências de loop válidas.
## Requirements
### Requirement: Configuração de sessão tmux
O sistema SHALL ler parâmetros da sessão tmux a partir de `[session]` no `sac.toml`.

#### Scenario: Seção session completa
- **GIVEN** um `sac.toml` com `[session]` contendo `name`, `notify_interval`, `poke_stale_after`, `boot_wait` e `socket`
- **WHEN** o arquivo é carregado
- **THEN** `session_name` é `"sac"`, `notify_interval` é 10, `poke_stale_after` é 10, `boot_wait` é 12, `socket` é `"~/.sac/tmux.sock"`

#### Scenario: Defaults aplicados
- **GIVEN** um `sac.toml` com `[session]` contendo apenas `name`
- **WHEN** o arquivo é carregado
- **THEN** os defaults são aplicados: `notify_interval=30`, `poke_stale_after=120`, `boot_wait=12`, `socket=None`

### Requirement: Declaração de agentes
O sistema SHALL aceitar múltiplos agentes declarados em `[[agents]]`, com papéis `leader` e `aux`, e suporte a `boot_wait` opcional por agente.

#### Scenario: Agente completo
- **GIVEN** `[[agents]]` com `name`, `command`, `args[]`, `role`, `prompt_file` e `boot_wait`
- **WHEN** o arquivo é carregado
- **THEN** o agente é configurado com todos os campos

#### Scenario: Agente sem prompt_file
- **GIVEN** `[[agents]]` sem `prompt_file`
- **WHEN** o arquivo é carregado
- **THEN** `prompt_file` é `None` e o agente não recebe injeção automática de prompt

#### Scenario: Agente sem boot_wait (usa global)
- **GIVEN** `[[agents]]` sem `boot_wait`
- **WHEN** o arquivo é carregado
- **THEN** o agente usa o valor global `[session].boot_wait` como default

#### Scenario: Nomes duplicados
- **GIVEN** `[[agents]]` com dois agentes de mesmo `name`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro de validação

#### Scenario: Role inválida
- **GIVEN** `[[agents]]` com `role` diferente de `"leader"` ou `"aux"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro de validação

### Requirement: Leader único
Exatamente um agente SHALL ter `role = "leader"`.

#### Scenario: Sem leader
- **GIVEN** `[[agents]]` sem nenhum agente com `role = "leader"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro

#### Scenario: Dois leaders
- **GIVEN** `[[agents]]` com dois agentes de `role = "leader"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro

### Requirement: Declaração de loops
O sistema SHALL aceitar loops de trabalho declarados em `[[loops]]`, com sequência de agentes e limite de iterações.

#### Scenario: Loop completo
- **GIVEN** `[[loops]]` com `name`, `sequence[]` e `max_iterations`
- **WHEN** o arquivo é carregado
- **THEN** `name` é o identificador, `sequence` é a lista ordenada de agentes, `max_iterations` é o limite máximo

#### Scenario: Loop sem max_iterations
- **GIVEN** `[[loops]]` sem `max_iterations`
- **WHEN** o arquivo é carregado
- **THEN** o default `max_iterations=3` é aplicado

#### Scenario: Agente desconhecido no loop
- **GIVEN** `[[loops]]` com `sequence` contendo um nome de agente que não existe em `[[agents]]`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro de validação

### Requirement: Acesso programático a agentes
O sistema SHALL expor métodos para lookup de agente por nome e acesso ao leader.

#### Scenario: Lookup por nome
- **WHEN** `config.agent("dev-1")` é chamado
- **THEN** retorna o `AgentConfig` correspondente ou lança erro se não existir

#### Scenario: Property leader
- **WHEN** `config.leader` é acessado
- **THEN** retorna o `AgentConfig` com `role = "leader"`

### Requirement: Geração de sac.toml via template
O sistema SHALL gerar um arquivo `sac.toml` válido a partir das respostas do
questionário `sac init`.

#### Scenario: Template gerado com valores do questionário
- **GIVEN** valores fornecidos pelo usuário: nome="minha-esteira", leader="lead",
  workers=["dev-1","auditor"], loop="dev-review"
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML contém `[session] name = "minha-esteira"`
- **AND** `[[agents]]` para cada worker com os campos fornecidos
- **AND** `[[loops]]` com o loop declarado
- **AND** o TOML é válido (parseável por `load_config`)

#### Scenario: Template sem loops
- **GIVEN** usuário não declara loops
- **WHEN** `sac init` gera o arquivo
- **THEN** o TOML não contém seção `[[loops]]`

### Requirement: Seção session com root opcional
O sistema SHALL aceitar campo `root` opcional na seção `[session]` do `sac.toml`
para definir a raiz explícita do diretório `.sac/`.

#### Scenario: Session com root
- **GIVEN** `[session]` contém `root = "/home/dev/Github"`
- **WHEN** o arquivo é carregado
- **THEN** `session.root` é `"/home/dev/Github"`
- **AND** o Store usa `/home/dev/Github/.sac` como diretório de mensageria

#### Scenario: Session sem root
- **GIVEN** `[session]` sem campo `root`
- **WHEN** o arquivo é carregado
- **THEN** `session.root` é `None`
- **AND** o Store usa o comportamento atual (cwd)

#### Scenario: Validação — root precisa ser caminho absoluto
- **GIVEN** `[session]` com `root = "relativo/path"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro: "root deve ser caminho absoluto"

### Requirement: Seção session com poke_escalate_after opcional
O sistema SHALL aceitar campo `poke_escalate_after` opcional na seção
`[session]` do `sac.toml`, definindo quantos pokes sem `done` disparam o
escalonamento automático ao líder (default 3).

#### Scenario: Session com poke_escalate_after
- **GIVEN** `[session]` contém `poke_escalate_after = 5`
- **WHEN** o arquivo é carregado
- **THEN** `session.poke_escalate_after` é `5`

#### Scenario: Session sem poke_escalate_after
- **GIVEN** `[session]` sem o campo
- **WHEN** o arquivo é carregado
- **THEN** `session.poke_escalate_after` é `3` (default)

#### Scenario: Validação — valor mínimo 1
- **GIVEN** `[session]` com `poke_escalate_after = 0`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com erro: "poke_escalate_after deve ser >= 1"

### Requirement: Seção [windows] opcional
O sistema SHALL aceitar uma seção `[windows]` no `sac.toml` onde cada chave é
o nome de uma window e o valor é um spec de layout (gramática `;`/`,`), e
SHALL validar a cobertura exata dos agentes declarados.

#### Scenario: Config com [windows] válido
- **GIVEN** 3 agentes (leader, dev-1, auditor) e
  `[windows]` com `main = "leader"` e `trabalho = "dev-1,auditor"`
- **WHEN** o arquivo é carregado
- **THEN** `cfg.windows` contém as duas entradas na ordem declarada

#### Scenario: Config sem [windows]
- **GIVEN** config sem a seção
- **WHEN** o arquivo é carregado
- **THEN** `cfg.windows` é vazio (layout legado)

#### Scenario: Agente desconhecido no spec
- **GIVEN** `[windows]` com `main = "leader;fantasma"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com ConfigError citando o agente desconhecido

#### Scenario: Agente duplicado nos specs
- **GIVEN** `[windows]` com `main = "leader"` e `x = "leader,dev-1"`
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com ConfigError (agente em mais de um pane)

#### Scenario: Agente ausente dos specs
- **GIVEN** 3 agentes e `[windows]` cobrindo apenas 2
- **WHEN** o arquivo é carregado
- **THEN** o sistema rejeita com ConfigError citando o agente ausente

### Requirement: Tamanho da sessão tmux no boot
O sistema SHALL permitir configurar o tamanho inicial da sessão tmux via `[session] width` e `[session] height` (inteiros positivos), com default de 220x50 quando ausentes.

#### Scenario: Defaults sem configuração
- **WHEN** o `sac.toml` não declara `width`/`height` em `[session]`
- **THEN** a config resultante usa width=220 e height=50

#### Scenario: Override explícito
- **WHEN** `[session]` declara `width = 180` e `height = 40`
- **THEN** a config resultante usa width=180 e height=40

#### Scenario: Valor inválido
- **WHEN** `width` ou `height` não é inteiro positivo
- **THEN** o sistema levanta ConfigError indicando a chave inválida

### Requirement: Init agnóstico de ambiente
O sistema SHALL gerar configuração e prompts sem referências a nenhum ambiente, harness configurado, alias de modelo ou caminho específico — o SAC é um gerenciador de harness agnóstico e toda escolha de modelo/comando é do usuário, via args do agente.

#### Scenario: Notas de harness sem modelo hardcoded
- **WHEN** `sac init` gera os prompts dos agentes
- **THEN** as notas de harness (kimi/opencode) descrevem o harness genericamente, sem indicar alias ou modelo específico

#### Scenario: Pergunta de modelo sem exemplo de ambiente
- **WHEN** o questionário pergunta o modelo de um agente
- **THEN** o exemplo exibido é genérico e a resposta vazia significa "não passar --model"

### Requirement: Wizard UX — hints, harness validation, onboarding checklist

O questionário do `sac init` SHALL estender o comportamento atual com três
melhorias de UX voltadas ao usuário iniciante: (1) hints explicativos por
pergunta, (2) validação de harness no momento da entrada, (3) checklist
pós-criação.

#### Scenario: Init imprime hint antes de cada pergunta

- **GIVEN** usuário executando `sac init` interativo
- **WHEN** o sistema pergunta o nome da sessão
- **THEN** antes da pergunta exibe uma linha de hint explicando o propósito
  (ex.: "nome para a sessão tmux — usado para attach e identify")
- **AND** o mesmo se aplica a todas as perguntas do questionário (socket,
  boot_wait, nome do agente, comando, papel, modelo, loops)

#### Scenario: Init valida command com shutil.which

- **GIVEN** usuário informa `command = "kimi"` para um agente
- **WHEN** o sistema recebe o valor
- **THEN** executa `shutil.which("kimi")`
- **AND** se não encontrado no PATH, exibe warning:
  `"⚠ harness 'kimi' não encontrado no PATH — você pode corrigir ou seguir
   assim (ex.: config para outra máquina)"`
- **AND** oferece opção de corrigir o comando ou confirmar com o valor atual
- **AND** o init continua sem abortar (não é erro fatal)

#### Scenario: Init comando não encontrado — usuário opta por seguir

- **GIVEN** warning de comando não encontrado exibido
- **WHEN** usuário opta por seguir com o valor atual
- **THEN** o init continua normalmente com o comando informado

#### Scenario: Init comando encontrado — sem warning

- **GIVEN** comando existe no PATH (`shutil.which` retorna caminho)
- **WHEN** o init processa o comando
- **THEN** nenhum warning é exibido

#### Scenario: Init exibe checklist pós-criação

- **GIVEN** `sac.toml` e `prompts/*.md` gerados com sucesso
- **WHEN** o init conclui
- **THEN** imprime checklist com 4 passos:

```
=== Próximos passos ===
1. Pre-warm: rode o harness 1x no diretório para aprovar plugins/login
   → kimi . (ou o comando do seu harness)
2. Edite os prompts com as regras do seu projeto:
   → prompts/*.md
3. Suba a esteira:
   → sac up
4. Acompanhe:
   → sac attach

Dica: configure o layout [windows] no sac.toml para agrupar agentes por função.
Veja o guia iniciante em docs/beginner-guide.md
```

### Requirement: README section "SAC and your harness"

O README do projeto SHALL conter uma seção (próximo ao bloco Concepts ou em
posição de destaque similar) documentando a fronteira entre SAC e o harness,
para eliminar dúvidas comuns de usuários iniciantes. A seção SHALL cobrir:

- **Plugins e skills funcionam sem configuração extra**: o SAC levanta o mesmo
  binário do harness do usuário — plugins/skills globais (`~/.kimi/plugins`,
  `~/.claude/skills`, `~/.config/opencode`) e de projeto (`.claude/skills`,
  `AGENTS.md`) são carregados pelo próprio harness, sem qualquer intervenção do
  SAC. O `prompt_file` não é configuração — é uma mensagem injetada no primeiro
  turno; nada é substituído ou desativado.
- **Tabela "o que vive onde"**: config de harness (plugins, skills, login,
  modelo, flags) = arquivos do próprio harness, gerenciados pelo usuário; config
  do SAC = `sac.toml` (agentes, papéis, layout, socket) + contratos de prompt
  (comportamento dos agentes).
- **Pre-warm**: antes do primeiro `sac up`, rodar o harness 1x no diretório do
  workspace para aprovar logins/plugins/consentimentos interativos — o SAC não
  responde diálogos do harness (e não deve).
- **Memória de longo prazo**: memória compartilhada entre agentes deve viver em
  arquivos do workspace (`AGENTS.md`, `handoff/`, `docs/`) — qualquer harness lê
  Markdown; plugins de memória são por harness e por processo, não compartilham
  entre agentes. A disciplina de ler/registrar fica nos contratos de prompt
  (filosofia: SAC entrega cartas; comportamento está nos manuais).
- **"Stupid" de propósito**: o SAC não configura o harness, não orquestra
  workflow, não impõe nada — só entrega mensagens. Toda inteligência está nos
  contratos e nas configs de cada camada.

#### Scenario: README contém seção "SAC and your harness"

- **GIVEN** o README do projeto
- **WHEN** um usuário iniciante lê
- **THEN** a seção "SAC and your harness" (ou título equivalente) está presente
- **AND** cobre: plugins/skills, tabela de config vs SAC, pre-warm, memória
  compartilhada, mantra "stupid"

#### Scenario: Seção menciona que plugins funcionam sem extra

- **GIVEN** a seção "SAC and your harness"
- **WHEN** o usuário busca sobre plugins/skills
- **THEN** o texto afirma que plugins e skills globais/de projeto funcionam sem
  configuração extra no SAC
- **AND** menciona que o `prompt_file` é uma mensagem, não substitui config

