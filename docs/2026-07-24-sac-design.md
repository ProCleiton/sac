# SAC — Stupid Agentic Coordinator — Design v1.2

Data: 2026-07-24 (revisão 2026-07-24: pivot daemon coordenador)
Status: Aprovado pelo usuário (direção geral + superfície v1)

## 1. Objetivo

Coordenador multi-agente minimalista, inspirado no CCB mas radicalmente mais simples.
Gerencia harnesses de IA (kimi, opencode, etc.) em panes tmux e fornece mensageria
entre eles com um **daemon opcional e leve** que entrega mensagens diretamente no
pane do agente: a "central" é um diretório no filesystem (`.sac/`), e o daemon é
apenas um entregador — sem banco, sem heurística de tela, sem estado interno.

Projeto paralelo de estudo. Stack: **Python 3 stdlib, zero dependências**.

## 2. Lição de design (origem)

O ponto mais frágil do CCB é a detecção de fim de turno por heurística de tela
(observada falhando 3× em 24/07 com kimi-code: jobs marcados `completed` por
`kimi_turn_end` no meio do trabalho, especialmente com tasks em background).
O SAC troca heurística por **contrato explícito**: o agente sinaliza conclusão
escrevendo a sentinela `SAC_DONE` e rodando `sac done <id>`.

O modelo notify original usava `sac next` + texto de aviso. O pivot para daemon
coordenador (v1.2) elimina a necessidade de o agente rodar `sac next` manualmente:
o daemon injeta o corpo da tarefa diretamente no pane, sem overhead de instrução.
O agente apenas vê a tarefa aparecer no terminal e trabalha — o contrato `SAC_DONE`
+ `sac done` permanece como único mecanismo de conclusão.

Metáfora da versão original: CCB = central telefônica com telefonista (processo
vivo, ponto único de falha). SAC = caixa de correio na porta de cada agente (ordem
e garantia vêm da física da caixa, não de alguém vigiando). Com o daemon, a caixa
de correio ganhou um carteiro que toca a campainha — mas a caixa continua sendo o
armazenamento fonte da verdade.

## 3. Arquitetura

### 3.1 Estado — todo em `.sac/` + a sessão tmux

```
.sac/
  inbox/<agente>/   # 1 arquivo por mensagem: <YYYYMMDD>-<HHMMSS>-<seq>-from-<origem>.msg
  claimed/<agente>/ # mensagem puxada via `sac next`, aguardando `sac done`
  done/<agente>/    # mensagens concluídas
  log.jsonl         # append-only: todo evento send/next/done/poke, auditável
```

- Ordem de chegada = ordem dos arquivos (timestamp + sequencial no nome).
- Fila natural: agente ocupado acumula mensagens na inbox; nada se perde.
- Crash do SAC não derruba nada: tmux e arquivos persistem; `sac up` é idempotente.

### 3.2 Daemon coordenador (opcional)

O SAC oferece um daemon leve (`sac daemon`, classe `Daemon` em `sac/daemon.py`)
que gerencia a entrega de mensagens aos agentes:

- **Polling**: a cada POLL_INTERVAL=1.0s, varre `inbox/` e `claimed/` de todos os
  agentes declarados no `sac.toml`.
- **Entrega direta**: se um agente tem mensagem pendente na inbox, o daemon injeta
  o **corpo da mensagem** diretamente no pane via `tmux send-keys -l` — sem texto
  "SAC: mensagem nova" ou `sac next`. O agente simplesmente vê a tarefa no terminal.
- **Re-cutucada de stale**: se um agente tem mensagem claimed há mais de
  `poke_stale_after` segundos sem `sac done`, o daemon re-injeta um lembrete:
  `"SAC: tarefa <id> pendente — rode \`sac done <id>\`"`.
- **PID file**: escreve `daemon.pid` em `.sac/` para que comandos como `sac send`
  saibam se o daemon está ativo e pulem o poke manual (evita double-poke).
- **Sem detecção de SAC_DONE**: o daemon não lê a saída do harness — evitar
  falso-positivos é prioridade de design.
- **SIGTERM/SIGINT**: encerramento limpo com remoção do PID file.

> O daemon é opcional. Se não estiver rodando, `sac send` faz o poke manual
> (legacy): injeta `"SAC: mensagem nova na inbox — rode \`sac next\`"`.
> Mensagens nunca se perdem — o filesystem é persistente com ou sem daemon.

### 3.3 Estado — todo em `.sac/` + a sessão tmux

## 4. Comandos (CLI `sac`)

| Comando | Quem usa | O que faz |
|---|---|---|
| `sac up` | usuário | Lê `sac.toml`, cria sessão tmux, sobe 1 pane por agente, injeta `prompt_file` de cada um, inicia dashboard com `sac log -f` + `sac daemon`. Idempotente (reattach se já existe). |
| `sac send <para> "<msg>"` | usuário, leader, auxiliares | Grava em `inbox/<para>/`, loga. Se daemon ativo (daemon.pid), pula poke manual. Senão, cutuca com "SAC: mensagem nova — rode `sac next`". |
| `sac next` | agente | Puxa a mensagem mais antiga da própria inbox (FIFO), move para `claimed/`, imprime id + conteúdo. (Útil quando daemon está offline.) |
| `sac done <id> "<resumo>"` | agente | Move a mensagem de `claimed/` para `done/`, loga. |
| `sac recv <agente>` | usuário, leader | Lê a resposta do agente: capture-pane desde o último `send` até a linha `SAC_DONE`. |
| `sac daemon` | uso interno | Daemon de mensageria (classe `Daemon`): poll de 1s, entrega direta + re-cutucada de stale. Sobe automaticamente na janela dash. |
| `sac notify [--once]` | usuário | Legado: varredura única (`--once`) ou loop de re-cutucada a cada `notify_interval`. Substituído pelo daemon. |
| `sac status` | usuário | Visão geral: agentes vivos (pane existe), inbox/claimed pendentes, daemon ativo (PID file). |
| `sac log [-f]` | usuário | Mostra (ou segue) o `log.jsonl`. |
| `sac attach` | usuário | Atacha à sessão tmux. |
| `sac down` | usuário | Encerra a sessão tmux (preserva `.sac/`). |
| `sac run <loop> "<tarefa>"` | usuário | Pontapé de um loop declarado: `send` no primeiro agente da sequência. |
| `sac sidebar` | interno | Renderiza sidebar com status dos agentes, inbox/claimed counts e atalhos tmux. |
| `sac inject <agente>` | usuário | Re-injeta o `prompt_file` de um agente no pane. |

## 5. `sac daemon` — coordenador de entrega

O daemon (`sac daemon`, classe `Daemon` em `sac/daemon.py`) substitui o watcher
`sac notify` como processo persistente. Diferenças vs. o modelo notify original:

| Aspecto | Notify (legado) | Daemon (v1.2) |
|---|---|---|
| Propósito | Re-cutucar mensagens stale | Entregar + re-cutucar |
| Poll interval | `notify_interval` (ex.: 30s) | 1s fixo (POLL_INTERVAL) |
| Entrega de msg nova | Apenas poke ("rode `sac next`") | Injeta corpo diretamente no pane |
| Stale detection | Mensagens em inbox+claimed > `poke_stale_after` | Mensagens claimed > `poke_stale_after` (injectadas pelo daemon não ficam stale) |
| Forma do poke stale | `"SAC: N mensagem(ns) aguardando — rode \`sac next\`"` | `"SAC: tarefa <id> pendente — rode \`sac done <id>\`"` |
| Embarque na dash | Pane `sac notify` (loop) | Pane `sac daemon` (poll de 1s) |

**Por que não detectar SAC_DONE automaticamente?** O daemon evita intencionalmente
ler a saída do harness (capture-pane). A heurística de tela é o ponto mais frágil
do CCB (falso-positivo: `kimi_turn_end` no meio do trabalho). O SAC mantém o
contrato explícito (`SAC_DONE` + `sac done`) mesmo com daemon — o agente que
conclui a tarefa manualmente.

## 6. Configuração (`sac.toml`)

```toml
[session]
name = "sac"
notify_interval = 30        # segundos entre varreduras do notify
poke_stale_after = 120      # re-cutuca se pendente/claimed há mais de 2min

[[agents]]
name = "leader"
command = "kimi"
args = ["--model", "esteira/k3"]
role = "leader"             # recebe os prompts do usuário
prompt_file = "prompts/leader.md"

[[agents]]
name = "dev-1"
command = "opencode"
args = ["-m", "opencode-go/deepseek-v4-flash"]
role = "aux"
prompt_file = "prompts/dev.md"

[[agents]]
name = "auditor"
command = "kimi"
args = ["--model", "esteira/k3"]
role = "aux"
prompt_file = "prompts/auditor.md"

[[loops]]
name = "dev-review"
sequence = ["leader", "dev-1", "auditor"]
max_iterations = 3
```

- **`role = "leader"`**: exatamente 1 por config; é o agente que recebe os prompts
  do usuário (`sac send leader "..."` / `sac run`).
- **`role = "aux"`**: auxiliares; recebem do leader e devolvem conforme contrato.
- **`[[loops]]`**: declara ciclos esperados (ex.: dev→auditor→dev no contra-fluxo
  de REPROVADO). O SAC **não enforce** o fluxo — quem executa é o contrato escrito
  no prompt de cada agente. A declaração serve para o `sac status` exibir o loop,
  para `sac run` saber onde dar o pontapé e para `max_iterations` constar no
  contrato como limite de segurança. Enforcement é candidato a v2.

## 7. Contrato de comunicação (injetado via `prompt_file`)

Todo agente recebe no prompt inicial:

1. Você faz parte de uma esteira coordenada pelo SAC. Tarefas chegam
   **automaticamente** no seu terminal (o daemon as injeta diretamente).
2. Para enviar a outro agente: `sac send <nome> "<mensagem>"`. O remetente é
   identificado pela variável de ambiente `SAC_AGENT` (definida pelo `env` no
   comando do pane), não "user" hardcoded.
3. Ao terminar de processar: (a) envie o resultado ao remetente original (campo
   `from:` da mensagem) via `sac send <remetente> "<resultado>"`; (b) escreva sua
   resposta no pane terminando com `SAC_DONE`; (c) rode `sac done <id> "<resumo>"`.
4. Sem `sac done`, o daemon re-cutucará periodicamente — é o comportamento esperado.
5. Se o daemon estiver offline, mensagens podem exigir `sac next` manual (poke
   "SAC: mensagem nova na inbox — rode `sac next`"). O prompt pode omitir este
   detalhe em favor de simplicidade.
6. O fluxo da esteira (quem entrega para quem, limites de iteração dos loops) está
   descrito no prompt específico de cada agente (`prompts/<agente>.md`).

## 8. Estrutura do código

```
sac/
  sac/
    __init__.py
    cli.py        # argparse, despacha para os comandos
    config.py     # parsing de sac.toml (tomllib)
    tmux.py       # wrapper fino dos comandos tmux (falso em testes)
    store.py      # inbox/claimed/done/log (filesystem)
    commands.py   # up/send/next/done/recv/notify/daemon/status/log/attach/down/run/sidebar/inject
    daemon.py     # Daemon: polling de 1s, entrega direta no pane + re-cutucada stale
  prompts/        # prompt_file de exemplo por papel
  tests/          # unittest; integração com tmux real marcada e opcional
  sac.toml        # config de exemplo
  pyproject.toml  # console_script `sac` (instalação opcional; também roda `python -m sac`)
```

Fronteira de teste: toda chamada tmux passa por `tmux.py`; os testes unitários
substituem por fake e cobrem store/commands/notify sem tmux real.

## 9. Testes

- stdlib `unittest` (zero deps), TDD do início.
- Unitários: config (toml válido/inválido), store (ordenação FIFO, next/done, log
  append-only), commands (send cutuca pane correto, recv para no SAC_DONE, notify
  re-cutuca só o que passou de `poke_stale_after`).
- Integração com tmux real: marcados, rodam sob demanda.

## 10. Fora de escopo (v1)

- Enforcement de loops (v2); detecção de pane ocupado/idle; delivery garantido além
  do filesystem; recovery de harness travado; UI/TUI própria; múltiplas sessões
  simultâneas (1 sessão por `sac.toml`). O daemon é uma adição leve que **não**
  quebra o modelo daemonless — continua rodando como processo opcional.

## 11. Decisões de documentação (24/07/2026)

- README em inglês (repositório público universal).
- Licença MIT — arquivo `LICENSE` na raiz do repo.
- Mascote: pombo carteiro gerado por IA (Pollinations.ai), creditado no README.
