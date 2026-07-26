## ADDED Requirements

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
