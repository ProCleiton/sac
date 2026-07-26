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
| `sac.toml` | O organograma (quem senta em qual mesa) |
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

## 3. Como configurar: o `sac.toml`

Tudo parte de um único arquivo `sac.toml` na raiz do workspace. Quatro seções:

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

### 3.4 `[[loops]]` — ciclos nomeados

Ver seção 5.

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

## 5. Loops (o sistema de "entrega" de ciclos)

Um `[[loop]]` é um **atalho nomeado** para disparar uma sequência de agentes:

```toml
[[loops]]
name = "dev-review"
sequence = ["lead", "dev-1", "auditor"]
max_iterations = 5
```

Dispara-se com:

```bash
sac run dev-review "feature Y"
```

**Ponto crucial para iniciantes**: o SAC **não enforce** o loop. Ele não força
o auditor a revisar, não conta iterações, não bloqueia nada. O loop real
acontece porque os **contratos de prompt** mandam — por exemplo, o contrato do
lead-coordinator o obriga a:

1. delegar implementação ao dev;
2. enviar o resultado ao `code-auditor` (gate de revisão);
3. se REPROVADO, re-delegar ao dev (máx. 3 iterações);
4. se APROVADO, seguir para os próximos gates (docs → secops → usuário → deploy).

Ou seja: o `[[loops]]` é **declaração + convenção**; a disciplina está nos
prompts. `max_iterations` documenta a intenção, quem impõe o limite é o contrato.

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
- Nomes de agentes no contrato devem bater com os `name` do `sac.toml` —
  é por esses nomes que os `sac send` roteiam.

---

## 7. Detalhe: `sac init` (o wizard)

O `sac init` é um **questionário interativo** (implementado em `sac/sac/init.py`)
que gera tudo que uma esteira precisa para nascer. **Requer terminal
interativo** (TTY) — em modo não-interativo ele aborta com a mensagem:

```
erro: init requer terminal interativo — use `sac --config <path>` para config existente
```

### 7.1 O que o wizard pergunta

1. **Nome da sessão** (default `sac`) — validado contra `[A-Za-z0-9_-]`.
2. **Socket tmux** (caminho; Enter = sem socket dedicado).
3. **Boot wait global** em segundos (default 10).
4. **Número de agentes** (default 3) e, para cada um:
   - nome (mesma validação);
   - comando (`kimi`/`opencode` — o primeiro agente tem default `kimi`);
   - papel (`leader`/`aux` — o primeiro é **forçado a leader**);
   - modelo (opcional; se preenchido, gera `args = ["--model", "<modelo>"]`;
     para `opencode` o wizard já acrescenta `--auto` automaticamente);
   - boot wait específico (Enter = usa o global).
5. **Loops** (opcional): nome, sequência de agentes separada por espaço
   (default: todos os aux), e `max_iterations` (default 3).

### 7.2 O que o wizard gera

| Artefato | Conteúdo |
|---|---|
| `sac.toml` | Config completa, com **validação round-trip** (o TOML gerado é re-parseado com `tomllib` antes de ser gravado; se inválido, o init aborta) |
| `prompts/<nome>.md` | Um por agente, a partir de templates internos (`LEADER_PROMPT` / `AUX_PROMPT`) + notas específicas do harness (`KIMI_NOTE` / `OPENCODE_NOTE`) |
| `.sac/` | Esqueleto de estado: `inbox/`, `claimed/`, `done/` |
| diretório do socket | Criado automaticamente se `socket` foi configurado |

### 7.3 Proteções do wizard

- **`sac.toml` já existe?** Pergunta "Sobrescrever? (s/N)" — default **não**.
- **`prompts/*.md` já existem?** Mesma pergunta, default **não** ("prompts
  mantidos").
- `Ctrl+C`/`EOF` no meio do questionário → "init cancelado pelo usuário", sem
  efeitos colaterais.

### 7.4 Os templates gerados

Os prompts gerados pelo `init` são **mínimos** (só o contrato SAC + notas do
harness). Exemplo do template de auxiliar:

```markdown
# Papel: aux (SAC)
Você é um auxiliar da esteira SAC. Tarefas chegam automaticamente.

## Contrato SAC (obrigatório)
- Tarefas chegam diretamente no seu terminal com cabeçalho `SAC <id> de <sender>:`.
- Ao concluir:
  1. Envie o resultado ao remetente com `sac send <remetente> "<resumo>"`.
  2. Escreva `SAC_DONE`.
  3. Rode `sac done <id> "<resumo>"`.
- Respostas que você receber são concluídas automaticamente — NÃO rode
  `sac done` nelas, apenas leia e aja.

## Notas do harness (opencode)
- opencode: respostas diretas e código.
- Use `--auto` para aprovação automática de comandos shell seguros.
```

Ou seja: o `init` dá o **esqueleto funcional**; as regras de negócio do
workspace (TDD, gates, estilo de commit) você adiciona depois editando os
`prompts/*.md` — como foi feito nos prompts deste workspace, que são bem mais
ricos que os templates.

---

## 8. Comandos do dia a dia

| Comando | Pra que serve |
|---|---|
| `sac up` | Sobe a sessão tmux com todos os agentes (idempotente, com barra de progresso 0–100% e log por agente) |
| `sac send <agente> "msg"` | Envia tarefa/mensagem |
| `sac send user "msg"` | Fala com o humano (ele lê via `sac log`) — funciona sem configurar "user" como agente |
| `sac run <loop> "tarefa"` | Dispara um loop declarado |
| `sac recv <agente>` | Lê uma resposta (até `SAC_DONE`) |
| `sac status` / `--mini` | Visão geral / resumo de uma linha (`2● 1!`) para a status bar |
| `sac status --clean [--yes]` | Lista/remove inbox+claimed órfãos de agentes que saíram do `sac.toml` (dry-run por padrão) |
| `sac sidebar --toggle` | Abre/fecha a sidebar na janela atual (bind `prefix+e`) |
| `sac log -f` | Acompanha o `log.jsonl` |
| `sac kill <agente>` | Reinicia um harness travado **in-place** (reinjeta prompt, re-alerta tarefas claimed) — sem ciclo down/up |
| `sac attach` | Entra na sessão tmux para olhar os panes |
| `sac daemon` | Roda o daemon de entrega (auto-iniciado no dash) |
| `sac down` | Desliga tudo: panes dos harnesses (em ordem), daemon (SIGTERM→SIGKILL via pid file) e sessão tmux |

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
