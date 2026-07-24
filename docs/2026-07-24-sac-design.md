# SAC — Stupid Agentic Coordinator — Design v1

Data: 2026-07-24
Status: Aprovado pelo usuário (direção geral + superfície v1)

## 1. Objetivo

Coordenador multi-agente minimalista, inspirado no CCB mas radicalmente mais simples.
Gerencia harnesses de IA (kimi, opencode, etc.) em panes tmux e fornece mensageria
entre eles **sem daemon**: a "central" é um diretório no filesystem.

Projeto paralelo de estudo. Stack: **Python 3 stdlib, zero dependências**.

## 2. Lição de design (origem)

O ponto mais frágil do CCB é a detecção de fim de turno por heurística de tela
(observada falhando 3× em 24/07 com kimi-code: jobs marcados `completed` por
`kimi_turn_end` no meio do trabalho, especialmente com tasks em background).
O SAC troca heurística por **contrato explícito**: o agente sinaliza conclusão
escrevendo a sentinela `SAC_DONE` e rodando `sac done <id>`.

Metáfora: CCB = central telefônica com telefonista (processo vivo, ponto único de
falha). SAC = caixa de correio na porta de cada agente (ordem e garantia vêm da
física da caixa, não de alguém vigiando).

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

### 3.2 Sem daemon

O SAC é um CLI efêmero. O único processo persistente além dos harnesses é o
`sac notify` (watcher burro, seção 5). Não há banco, fila em memória ou estado
oculto: tudo se inspeciona com `ls`/`cat`.

## 4. Comandos (CLI `sac`)

| Comando | Quem usa | O que faz |
|---|---|---|
| `sac up` | usuário | Lê `sac.toml`, cria sessão tmux, sobe 1 pane por agente, injeta `prompt_file` de cada um. Idempotente (reattach se já existe). |
| `sac send <para> "<msg>"` | usuário, leader, auxiliares | Grava em `inbox/<para>/`, loga, cutuca o pane ("SAC: mensagem nova — rode `sac next`"). |
| `sac next` | agente | Puxa a mensagem mais antiga da própria inbox (FIFO), move para `claimed/`, imprime id + conteúdo. |
| `sac done <id> "<resumo>"` | agente | Move a mensagem de `claimed/` para `done/`, loga. |
| `sac recv <agente>` | usuário, leader | Lê a resposta do agente: capture-pane desde o último `send` até a linha `SAC_DONE`. |
| `sac notify` | usuário (sobe 1x) | Loop watcher: re-cutuca agente com mensagem pendente/claimed sem `done` há mais de `poke_stale_after` segundos. Intervalo `notify_interval`. |
| `sac status` | usuário | Visão geral: agentes vivos (pane existe), inbox/claimed pendentes, última atividade. |
| `sac log [-f]` | usuário | Mostra (ou segue) o `log.jsonl`. |
| `sac attach` | usuário | Atacha à sessão tmux. |
| `sac down` | usuário | Encerra a sessão tmux (preserva `.sac/`). |
| `sac run <loop> "<tarefa>"` | usuário | Pontapé de um loop declarado: `send` no primeiro agente da sequência. |

## 5. `sac notify` (peça fundamental, incluída no MVP)

Loop em foreground (roda num pane próprio da sessão ou em background via shell):

1. A cada `notify_interval` segundos, varre `inbox/` e `claimed/` de todos os agentes.
2. Mensagem pendente ou claimed há mais de `poke_stale_after` segundos sem `done`
   → re-cutuca o pane do agente.
3. Cutucar é inofensivo por construção: o texto apenas enfileira no input do harness.

Não tenta detectar "turno ocupado" (essa é a heurística frágil que o SAC evita).
Prefere cutucar de mais a vigiar de menos.

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

1. Você faz parte de uma esteira coordenada pelo SAC. Mensagens chegam pela sua
   inbox; quando cutucado, rode `sac next` para puxar a mais antiga.
2. Para enviar a outro agente: `sac send <nome> "<mensagem>"`. O remetente é
   identificado pela variável de ambiente `SAC_AGENT` (definida pelo `env` no
   comando do pane), não "user" hardcoded.
3. Ao terminar de processar: (a) envie o resultado ao remetente original (campo
   `from:` da mensagem) via `sac send <remetente> "<resultado>"`; (b) escreva sua
   resposta no pane terminando com `SAC_DONE`; (c) rode `sac done <id> "<resumo>"`.
4. Sem `sac done`, o notify re-cutucará periodicamente — é o comportamento esperado.
5. O fluxo da esteira (quem entrega para quem, limites de iteração dos loops) está
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
    commands.py   # up/send/next/done/recv/notify/status/log/attach/down/run
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
  simultâneas (1 sessão por `sac.toml`).

## 11. Decisões de documentação (24/07/2026)

- README em inglês (repositório público universal).
- Licença MIT — arquivo `LICENSE` na raiz do repo.
- Mascote: pombo carteiro gerado por IA (Pollinations.ai), creditado no README.
