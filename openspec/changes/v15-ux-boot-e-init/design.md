## Context

SAC v1.4 foi arquivada com 6 specs. O usuário configurou uma esteira de 8
agentes e tomou 2 problemas de UX: falso sucesso no up (socket sem diretório)
e zero feedback durante ~80s de boot. A v1.5 endereça os 4 itens.

Stack: Python 3.11+ stdlib, tmux ≥ 3.0 (testes com pytest). Suíte: 167 passed.

## Goals / Non-Goals

**Goals:**
- Feedback por agente durante `sac up` (N/total + ação)
- Fail-fast em comandos tmux críticos com mensagem clara + sugestão
- `mkdir -p` automático do diretório do socket no up
- `sac init`: questionário interativo que gera sac.toml + prompts (stdlib only)

**Non-Goals:**
- Não mudar a API de Tmux._run() (método check() novo, _run inalterado)
- Não adicionar dependências (sem questionary/rich)
- init não valida harness externo (só pergunta e registra)
- init não gera prompts além do contrato SAC básico

## Decisions

### D1. Progresso no up — formato [N/total] nome: ação

- **Escolha**: imprimir `[3/8] development-specialist-1: criando janela...`
  antes de cada chamada tmux que cria janela/split; `[3/8] dev-1:
  aguardando 12s para injetar prompt...` antes do sleep; `[3/8] dev-1:
  prompt injetado.` após. Mesma linha, sem \n entre ação e conclusão.
- **Alternativa**: barra de progresso estilo `[###···]` com carriage return.
  Mais complexo, sem ganho real sobre texto simples.
- **Motivo**: formato simples, legível em log, compatível com output
  redirecionado. O CID (N/total) dá a sensação de avanço.

### D2. Fail-fast — TmuxError + check()

- **Escolha**: `Tmux` ganha `TmuxError` (exception). Novo método
  `check(*args)` que chama `_run()` e levanta `TmuxError(stderr)` se
  rc≠0. `cmd_up` usa `check()` para operações críticas (new_session,
  new_window, split_window). Operações tolerantes (resize_pane,
  kill_pane, send_keys) continuam com `_run()` e ignoram rc.
- **Onde se aplica**: up (todo), down (kill_session), kill (kill_pane é
  tolerante, mas find_pane_id não — usa _run com parse, se falhar não
  acha pane → erro natural). No up, se falhar na criação do leader, o
  erro é imediato — o usuário não espera 80s para descobrir.
- **Onde NÃO se aplica**: has_session (rc≠0 = False, não erro),
  send_keys (benigno), resize_pane (idem), kill_pane (benigno),
  paste/capture_pane (fallback silencioso aceitável).
- **Tratamento no CLI**: `main()` captura `TmuxError` e imprime:
  `"erro tmux: <stderr> — verifique o socket em <cfg.socket>"`.

### D3. mkdir -p do socket dir

- **Escolha**: em `cmd_up`, antes do `has_session`, se `cfg.socket`
  está definido: `Path(cfg.socket).parent.mkdir(parents=True,
  exist_ok=True)`.
- **Alternativa**: em `load_config` ou `Tmux.__init__`. Mas só faz
  sentido criar o dir quando for usar (no up).
- **Motivo**: 1 linha, elimina a causa raiz do falso sucesso.

### D4. sac init — questionário com input() puro

- **Escolha**: stdin injection pattern. `cmd_init(stdin=input,
  stdout=print)` aceita funções como dependências. Em produção usa
  `input()` e `print()`; em testes usa `StdinFake` que retorna
  respostas programadas.
- **Módulo**: `sac/init.py` — contém `cmd_init()`, funções de
  pergunta, e templates de prompt. Templates podem ser strings
  embutidas (contrato SAC básico) ou geradas a partir de `AgentConfig`.
- **Formato das perguntas**: print da pergunta + input(). Defaults
  entre colchetes: `Nome da sessão [sac]: `. Enter vazio aceita default.
- **Geração de prompts**: para cada agente, um arquivo
  `prompts/<nome>.md` com o contrato SAC básico adaptado ao papel
  (leader vs aux) e harness (kimi vs opencode).
- **Justificativa para não usar lib externa**: zero-dependências é
  uma restrição de design do projeto. input()/print() são suficientes
  para um questionário linear de ~15 perguntas.
- **Não interativo**: se `not sys.stdin.isatty()`, imprime erro e
  exit 1. `--yes` flag futura (fora de escopo desta change).

### D5. Templates de prompt — embutidos vs arquivos

- **Escolha**: templates embutidos em `sac/init.py` como dicionário
  de strings. `PROMPT_TEMPLATES = {"leader": "...# Papel: leader...",
  "aux": "...", "kimi": "...", "opencode": "..."}`. O init combina
  papel + harness para gerar o prompt final.
- **Alternativa**: arquivos em `sac/prompts/` do pacote. Polui o
  pacote com templates que só o init usa.
- **Motivo**: strings embutidas são auto-contidas, fáceis de testar,
  e não poluem o filesystem do pacote. O contrato SAC básico tem
  ~20 linhas — tamanho aceitável.

## Risks / Trade-offs

- **[R1] check() pode quebrar comandos que hoje são tolerantes**:
  risco baixo — a escolha de quais comandos usam check() é explícita
  (up/down/init). Comandos de runtime (daemon, send) continuam
  tolerantes.
- **[R2] init gera prompts genéricos**: o usuário pode precisar
  editar manualmente. Aceitável — init é ponto de partida. Prompts
  específicos (ex.: fluxo dev-review) sempre exigiram edição manual.
- **[R3] input() não tem validação**: se o usuário digitar um nome
  inválido (ex.: "foo bar" — com espaço), o sac.toml pode ser
  inválido. Mitigação: validar entradas críticas (nome sem espaços)
  e repetir a pergunta se inválida.

## Rollback Plan

1. **Progresso**: reverter cmd_up para o loop silencioso.
2. **Fail-fast**: remover check() e TmuxError; restaurar cmd_up sem
   tratamento de rc.
3. **mkdir socket**: remover linha do cmd_up.
4. **init**: remover `sac/init.py`, `tests/test_init.py`, parser cli.
