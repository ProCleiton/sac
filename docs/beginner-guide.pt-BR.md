# SAC — Guia do Usuário Iniciante

> **SAC = Stupid Agentic Coordinator** — coordenador multi-agente minimalista,
> escrito em Python 3 (somente stdlib) + tmux.
> Fonte: repositório `sac/` (README, `sac/sac/init.py`) e `sac.toml` do workspace.

---

## 1. O que é o SAC

O SAC coloca vários harnesses de IA (Kimi Code, opencode...) para rodar em panes
de uma sessão tmux, cada um com um **papel** (líder, dev, auditor, docs, deploy...),
e cuida de **uma coisa só**: entregar mensagens entre eles.

Ele é "stupid" de propósito:

- **Não** tenta adivinhar quando um agente terminou (sem heurísticas de tela).
- **Não** orquestra lógica de negócio nem enforce workflows.
- Só garante a **entrega das cartas** (caixa de correio em filesystem + daemon).

A inteligência do workflow vive nos **prompts de contrato** (`prompts/*.md`) —
é lá que se define, por exemplo, que o lead deve mandar o trabalho do dev para
o auditor antes de aprovar.

### A metáfora

Pense numa repartição pública com caixas de correio:

| Peça do SAC | Na metáfora |
|---|---|
| `.sac/sac.toml` | O organograma (quem senta em qual mesa) |
| `prompts/*.md` | O manual de conduta de cada funcionário |
| daemon (`sac daemon`) | O motoboy que leva os ofícios de mesa em mesa |
| `.sac/` | O arquivo morto onde tudo fica registrado |

O SAC garante que as cartas cheguem; o que cada funcionário faz com elas é
responsabilidade do manual dele.

---

## 2. Instalação

```bash
pipx install -e .          # recomendado — isola o SAC num venv próprio
# ou
pip install --user -e .    # pode precisar de --break-system-packages no Ubuntu 24.04+
```

Pré-requisitos: Python 3 e tmux.

---

## 3. Como configurar: o `.sac/sac.toml`

Tudo parte de um único arquivo de configuração. Desde a v24 o local padrão é
`.sac/sac.toml` (dentro do diretório oculto de estado); um `sac.toml` legado na
raiz do workspace é **ignorado** desde a v25 — a ordem de descoberta é: flag
`--config` → `$SAC_CONFIG` → `./.sac/sac.toml`. Para migrar um workspace
antigo: `mkdir -p .sac && mv sac.toml .sac/`. Três seções:

### 3.1 `[session]` — a sessão tmux

```toml
[session]
name = "esteira"                        # nome da sessão tmux
notify_interval = 10
poke_stale_after = 120                  # segundos até re-cutucar tarefa parada
boot_wait = 8                           # espera antes de injetar o prompt (s)
socket = "~/.sac-esteira/tmux.sock"     # socket tmux dedicado
```

- `socket`: cada esteira usa seu próprio socket tmux — nunca o socket default.
- `width`/`height` (opcionais, default 220x50): geometria da sessão, evita
  SIGILL em panes estreitos no boot.

### 3.2 `[[agents]]` — um bloco por agente

```toml
[[agents]]
name = "lead"
command = "kimi"                                   # harness: kimi, opencode...
args = ["--model", "kimi-code/k3", "--yolo"]       # flags do harness
role = "leader"                                    # exatamente UM leader por config
prompt_file = "prompts/lead-coordinator.md"        # o "manual de conduta"
boot_wait = 6                                      # opcional: sobrepõe o global
```

- `role`: `leader` (orquestrador) ou `aux` (trabalhador). **Deve existir
  exatamente um `leader`.**
- `boot_wait` individual: útil porque harnesses diferentes abrem em velocidades
  diferentes (opencode costuma precisar de menos espera que o kimi, por exemplo).

### 3.3 `[windows]` — layout visual (estilo CCB)

```toml
[windows]
main     = "lead"                    # 1 pane só
trabalho = "dev-1,dev-2"             # vírgula = empilha vertical
apoio    = "docs;auditor"            # ponto-e-vírgula = lado a lado
ops      = "deployment;secops;revisor"
```

Gramática: `,` empilha verticalmente, `;` divide lado a lado. Toda janela ganha
uma **sidebar viva** à esquerda (árvore de janelas → agentes, badges de inbox,
tempo ocioso, últimos eventos). A janela `dash` é sempre criada. Sem `[windows]`,
vale o layout legado de uma janela por agente.

---

## 4. O sistema de entrega (mailbox + daemon)

O coração do SAC é uma **caixa de correio em filesystem**, dentro de `.sac/`:

```
.sac/
  inbox/<agente>/    ← mensagens novas
  claimed/<agente>/  ← tarefa em andamento
  done/<agente>/     ← histórico
  log.jsonl          ← log de todos os eventos
```

### Ciclo de vida de uma mensagem

1. Alguém roda `sac send dev-1 "implemente X"` → cai um arquivo em `inbox/dev-1/`.
2. O **daemon** (`sac daemon`, polling a cada 1s) vê a mensagem e **injeta o
   corpo direto no pane tmux** do dev-1 via `send-keys`. O agente não precisa
   ficar perguntando "chegou algo?" — a tarefa aparece no terminal dele com o
   cabeçalho `SAC <id> de <sender>:` na primeira linha.
3. O agente trabalha e, ao concluir:
   1. responde ao remetente: `sac send <remetente> "<resultado>"`;
   2. escreve `SAC_DONE` numa linha separada;
   3. roda `sac done <id> "<resumo>"`.
4. **Respostas** (o campo `reply_to` é inferido no envio) são especiais: furam
   a fila mesmo com o agente ocupado e são **auto-concluídas** — não precisam
   de `sac done`. Só tarefas novas exigem conclusão explícita.

### Robustez

- **Sem daemon, nada se perde**: se o daemon cair, `sac send` cai no modo legado
  ("SAC: mensagem nova — rode `sac next`"). O inbox persiste em disco,
  independente do daemon ou do tmux.
- **Backoff exponencial**: o daemon dobra o intervalo entre pokes na mesma
  tarefa parada (base `poke_stale_after`, teto de 5 min) — evita tempestade de
  cutucadas em tarefas longas.
- **`sac up` é idempotente**: crash do SAC ou do daemon não derruba nada.

---

## 5. Loops — removidos na v26b (breaking change)

Os loops declarados (`[[loops]]` + o comando `sac run`) foram **removidos na
v26b**, sem período de deprecação: um config contendo `[[loops]]` para de
carregar com um erro claro — remova a seção do seu `sac.toml`.

A delegação e os ciclos de revisão viraram **disciplina do contrato do líder**:
o líder decompõe o trabalho, delega com `sac send <aux> "<tarefa>"`, cobra
revisão do trabalho dos auxiliares (revisando ele mesmo ou delegando a um aux
revisor) e itera delegar → revisar → corrigir até o resultado convergir —
escalando ao usuário só em bloqueio real. O contrato de líder gerado
(`prompts/<lider>.md`) já traz essa disciplina; nada mais é necessário.

---

## 6. Detalhe: os `prompt_file` (contratos de agente)

O `prompt_file` de cada agente é o arquivo Markdown injetado no harness no boot
(`sac up` espera `boot_wait` segundos e injeta o conteúdo no pane). É ele quem
transforma um harness genérico em "dev-1" ou "auditor". **O SAC entrega
mensagens; o contrato define comportamento.**

### 6.1 Anatomia de um contrato

Todo prompt de contrato tem, no mínimo, três partes:

1. **Papel** — quem o agente é na esteira. Ex.: "Você é um desenvolvedor da
   esteira SAC. Implementa com TDD."
2. **Contrato SAC (obrigatório)** — as regras mecânicas de comunicação:
   - tarefas chegam com cabeçalho `SAC <id> de <sender>:`;
   - o `<remetente>` para `sac send` e o `<id>` para `sac done` vêm desse
     cabeçalho;
   - ao concluir: `sac send <remetente> "<resumo>"` → `SAC_DONE` →
     `sac done <id> "<resumo>"`;
   - respostas recebidas são auto-concluídas — **não** rodar `sac done` nelas;
   - se o remetente for `user`, responder com `sac send user "<mensagem>"`.
3. **Regras do workspace** — as convenções do projeto (TDD, separação de
   camadas, soft delete, prefixos de commit, proibição de `git push` sem
   autorização, etc.).

### 6.2 Exemplo real (resumo de `prompts/development-specialist-1.md`)

```markdown
# Papel: development-specialist (SAC)
Você é um desenvolvedor da esteira SAC. **Implementa com TDD**...

## Contrato SAC (obrigatório)
- Tarefas chegam com cabeçalho `SAC <id> de <sender>:`.
- Ao concluir:
  1. Envie o resultado ao remetente com `sac send <remetente> "<resumo>"`.
  2. Escreva `SAC_DONE`.
  3. Rode `sac done <id> "<resumo>"`.
- Respostas que você receber são concluídas automaticamente — NÃO rode
  `sac done` nelas.

## Regras do workspace
- TDD obrigatório: sem testes = sem merge.
- Soft delete: `dt_exclusao` em vez de DELETE físico.
- NUNCA `git push` sem autorização.
```

### 6.3 O contrato do leader é diferente

O prompt do líder adiciona a **orquestração e os gates** — é nele que o loop
"dev → auditor → docs → deploy" é de fato implementado:

- delegar implementação aos devs;
- **gate code-auditor** (revisão; REPROVADO → re-delega, máx. 3 iterações);
- **gate information-specialist** (documentação);
- **gate secops-analyst** (se tocar segredos/auth/dados pessoais);
- pedir autorização ao usuário (`sac send user`);
- delegar o ciclo Git ao `deployment-officer`;
- solicitar archive ao `information-specialist`.

O líder também é o **único canal com o humano** — os workers se reportam a ele,
nunca ao usuário diretamente.

### 6.4 Boas práticas ao escrever um contrato

- Seja **mecânico e imperativo** na parte SAC (os agentes precisam executar
  `sac send`/`sac done` sem ambiguidade).
- Deixe explícito **para quem** o agente reporta e **quando** pedir gate.
- Repita as regras críticas do workspace (o prompt é a única "memória" garantida
  do agente no boot).
- Nomes de agentes no contrato devem bater com os `name` do `.sac/sac.toml` —
  é por esses nomes que os `sac send` roteiam.

---

## 7. Detalhe: `sac init` (o wizard)

O `sac init` é um **questionário interativo** (implementado em `sac/sac/init.py`)
que gera tudo que uma esteira precisa para nascer — sem ida ao repositório:
toda pergunta tem hint com exemplo concreto. **Requer terminal interativo**
(TTY) — em modo não-interativo ele aborta com a mensagem:

```
erro: modo interativo requer terminal — use --config para apontar um sac.toml existente
```

O wizard abre anunciando o que será gerado e onde:

```
SAC init — este wizard gera:
  .sac/sac.toml   (configuração da esteira)
  .sac/           (estado: inbox/claimed/done)
  prompts/*.md    (contrato de cada agente — edite à vontade depois)
```

### 7.1 O que o wizard pergunta

1. **Nome da sessão** (default `sac`) — validado contra `[A-Za-z0-9_-]`; o hint
   mostra onde o nome aparece (`sac attach`, `tmux ls`).
2. **Socket tmux** (caminho; Enter = sem socket dedicado) — hint com exemplo
   concreto (`~/.sac-nfi/tmux.sock`).
3. **Boot wait global** em segundos (default 10) — hint com faixa sugerida.
4. **Número de agentes** (default 3) e, para cada um:
   - **o agente 1 é anunciado como leader/orquestrador** (header + hint do
     papel) — **não há pergunta de papel**; agentes 2+ viram `aux`
     automaticamente;
   - nome (mesma validação);
   - comando — o default é o **primeiro harness detectado no PATH**
     (kimi → opencode → claude, com hint "detectado no seu PATH"); sem
     detecção, cai no placeholder fixo (`kimi` para o agente 1, `opencode`
     para os demais). Comando desconhecido gera warning com opção de corrigir
     ou seguir;
   - **contrato** (só agentes 2+): catálogo numerado — ver 7.4; o agente 1
     recebe o contrato de líder sem pergunta;
   - modelo (opcional; se preenchido, gera `args = ["--model", "<modelo>"]`;
     para `opencode` o wizard já acrescenta `--auto` automaticamente);
   - boot wait específico (Enter = usa o global).
5. **Agrupamento em janelas** (opcional, default não): por janela — nome,
   agentes (separados por espaço, validados contra os criados) e disposição
   (`1` lado a lado → `;`, `2` empilhados → `,`), com preview antes de
   perguntar pela próxima janela. Agentes fora de qualquer janela ficam com
   janela própria.

### 7.2 O que o wizard gera

| Artefato | Conteúdo |
|---|---|
| `.sac/sac.toml` | Config completa, com **validação round-trip** (o TOML gerado é re-parseado com `tomllib` antes de ser gravado; se inválido, o init aborta) |
| `prompts/<nome>.md` | Um por agente: o contrato canônico do papel escolhido (protocolo de mensageria SAC + disciplina do papel) + notas específicas do harness (`KIMI_NOTE` / `OPENCODE_NOTE`) |
| `.sac/` | Esqueleto de estado: `inbox/`, `claimed/`, `done/` |
| diretório do socket | Criado automaticamente se `socket` foi configurado |

### 7.3 Proteções do wizard

- **Config já existe** (`.sac/sac.toml` ou `sac.toml` legado)? Pergunta
  "Sobrescrever? (s/N)" — default **não**.
- **`prompts/*.md` já existem?** Mesma pergunta, default **não** ("prompts
  mantidos").
- `Ctrl+C`/`EOF` no meio do questionário → "init cancelado pelo usuário", sem
  efeitos colaterais.

### 7.4 O catálogo de contratos canônicos

O catálogo (dados puros em `sac/sac/contracts.py`) tem 7 papéis. Cada contrato =
o **protocolo de mensageria SAC** (inbox / `sac next` / reply / `sac done`) +
a **disciplina do papel**, em texto puro que **não exige plugin nem CLI
externo**:

| # | Papel | Disciplina |
|---|-------|-----------|
| 1 | líder/orquestrador | recebe do usuário, decompõe, delega, consolida; escala bloqueios |
| 2 | desenvolvedor (default dos aux) | TDD (teste antes), mudanças mínimas, debugging sistemático antes de propor fix |
| 3 | revisor de código | veredito por evidência (roda a suíte, lê o diff); bloqueantes vs. warnings |
| 4 | documentação | docs fiéis ao código; OpenSpec atualizado |
| 5 | deploy/release | ciclo git por etapas com autorização; CI verde antes de merge |
| 6 | segurança | threat modeling do diff, segredos, superfícies de entrada |
| 7 | auxiliar genérico | contrato SAC básico (mensageria + `SAC_DONE`), sem disciplina extra |

As disciplinas são inspiradas no plugin de skills **superpowers** e no workflow
**OpenSpec** — a stack canônica do SAC — mas funcionam sem nada disso
instalado. Editar um contrato depois = abrir o `prompts/<nome>.md` no editor;
o wizard nunca reedita contratos.

Ou seja: o `init` entrega um **esqueleto funcional com disciplinas reais**; as
regras de negócio específicas do projeto você adiciona editando os
`prompts/*.md`.

### 7.5 Começar do zero: `sac uninstall`

O `sac uninstall` remove a configuração do SAC do workspace atual, com
segurança:

1. **Recusa se a sessão tmux estiver no ar** — rode `sac down` antes;
2. **Lista o que será removido**: `.sac/` (config + estado), `prompts/` e o
   `sac.toml` legado, se existir;
3. **Exige digitar o nome da sessão** para confirmar — qualquer outra entrada
   aborta sem remover nada.

Nada fora do diretório do workspace é tocado, e nenhum processo é morto.

---

## 8. Comandos do dia a dia

| Comando | Pra que serve |
|---|---|
| `sac up` | Sobe a sessão tmux com todos os agentes (idempotente, com barra de progresso 0–100% e log por agente) |
| `sac send <agente> "msg"` | Envia tarefa/mensagem |
| `sac send user "msg"` | Fala com o humano (ele lê via `sac log`) — funciona sem configurar "user" como agente |
| `sac recv <agente>` | Lê uma resposta (até `SAC_DONE`) |
| `sac status` / `--mini` | Visão geral / resumo de uma linha (`2● 1!`) para a status bar |
| `sac status --clean [--yes]` | Lista/remove inbox+claimed órfãos de agentes que saíram do `sac.toml` (dry-run por padrão) |
| `sac sidebar --toggle` | Abre/fecha a sidebar na janela atual (bind `prefix+e`) |
| `sac log -f` | Acompanha o `log.jsonl` |
| `sac kill <agente>` | Reinicia um harness travado **in-place** (reinjeta prompt, re-alerta tarefas claimed) — sem ciclo down/up |
| `sac attach` | Entra na sessão tmux para olhar os panes |
| `sac daemon` | Roda o daemon de entrega (auto-iniciado no dash) |
| `sac doctor` | Diagnóstico read-only do ambiente: Python, tmux, socket, config (informa qual arquivo foi usado, avisa ambiguidade), harnesses e o CLI `openspec` |
| `sac down` | Desliga tudo: panes dos harnesses (em ordem), daemon (SIGTERM→SIGKILL via pid file) e sessão tmux |
| `sac uninstall` | Remove `.sac/`, `prompts/` e `sac.toml` legado — recusa com a sessão no ar, exige digitar o nome da sessão |
| `sac memory <sub>` | Memória de longo prazo do workspace (`.sac/memory.db`): `remember`, `recall`, `revise`, `forget`, `restore`, `decay`, `export`, `pack` |

### 8.1 Memória de longo prazo (`sac memory`)

Agentes não têm memória além da sessão — a menos que registrem. O SAC mantém
uma memória por workspace em `.sac/memory.db` (SQLite, só stdlib; busca FTS5
com degradação automática para `LIKE`). Toda memória tem um kind em pt-BR —
`tarefa`, `lição` ou `referência` — e importância de 1 a 5:

```bash
sac memory remember tarefa "Migrar esteira para config oculto" -i 4
sac memory remember lição "Archive OpenSpec exige nomes originais" -c "detalhe..."
sac memory recall "porta 9000"        # busca FTS5; sem query, as mais recentes
sac memory revise 7 -c "conteúdo atualizado"   # a antiga fica superada
sac memory forget 12                  # soft-delete (nunca DELETE físico)
sac memory restore 12
sac memory decay --days 30 --dry-run  # poda determinística; sem --dry-run, arquiva
sac memory export > memoria.md        # Markdown agrupado por kind
sac memory export --history           # auditoria de toda operação
```

O líder é o **curador**: o contrato dele ganha uma seção entre os marcadores
`<!-- SAC-MEMORY:BEGIN/END -->` com as memórias ativas (orçamento de ~4000
caracteres: tarefas → lições → referências, importância desc). O `sac up` e
cada escrita do `sac memory` reescrevem só esse trecho — contratos sem os
marcadores nunca são tocados. Toda mudança de estado fica auditada na tabela
`history` (visível via `export --history`).

Dica: dentro dos panes, as variáveis `SAC_ROOT` e `SAC_CONFIG` já estão
setadas — comandos `sac` funcionam de qualquer diretório dentro da sessão.

---

## 9. Referências

- Repositório: `sac/` (README completo em `sac/README.md`)
- Design doc: `sac/docs/2026-07-24-sac-design.md`
- Plano de implementação: `sac/docs/2026-07-24-sac-implementation-plan.md`
- Código do wizard: `sac/sac/init.py`
- Contratos reais deste workspace: `prompts/*.md`
- Inspiração: projeto **CCB (Claude Code Bridge)** — o SAC reimplementa a ideia
  na forma mais simples possível, trocando o daemon com detecção de estado de
  tela pela mailbox em filesystem + contrato explícito de sentinela (`SAC_DONE`).
