## Why

Ao configurar uma réplica da esteira CCB com SAC (8 agentes), o usuário tomou 2
problemas de UX: (1) `sac up` falhou silenciosamente porque o diretório-pai do
socket (~/.sac-esteira/) não existia — nenhum comando tmux funcionou, mas o
processo dormiu pelos boot_waits e imprimiu "sessão no ar" falso; (2) durante
~80s de boot sequencial, zero feedback — o usuário achou que travou. Além
disso, não há assistente para criar `sac.toml` e prompts do zero, o que seria
útil para novos workspaces.

## What Changes

- **Progresso no `sac up`**: imprimir `[N/total] agent: criando janela...
  aguardando Xs para prompt...` durante o boot. O usuário vê exatamente onde
  estamos e quanto falta.
- **Fail-fast em erros tmux**: `Tmux._run()` expõe método `check()` equivalente
  que levanta `TmuxError` se rc≠0. `cmd_up` (e comandos críticos: down, status)
  usam check() e abortam com mensagem clara do problema + sugestão de correção.
  Comandos tolerantes (kill_pane, resize_pane) mantêm o comportamento atual.
  `TmuxError` tratado no `cli.py`.
- **Criar diretório-pai do socket**: no `cmd_up`, se `cfg.socket` definido,
  `Path(cfg.socket).parent.mkdir(parents=True, exist_ok=True)` antes do
  primeiro comando tmux.
- **`sac init`**: questionário interativo que gera `sac.toml` + `prompts/*.md`
  com contrato SAC básico. Input() puro (zero dependências). Não-interativo:
  se stdin não é TTY, imprime erro orientando uso de --config. Testável via
  injeção de input/print.

## Capabilities

### New Capabilities
- `init`: assistente de configuração interativo (gera sac.toml + prompts)

### Modified Capabilities
- `cli`: comando `init` adicionado; `up` ganha flag --progress/feedback
- `sessao-tmux`: progresso no boot, fail-fast, socket dir criado
- `config`: geração de sac.toml no init

## Impact

**Código**: `sac/commands.py` (cmd_up com progresso/abort, cmd_init),
`sac/cli.py` (parser init), `sac/tmux.py` (TmuxError, check()),
`sac/init.py` (novo módulo: questionário + templates), `sac/config.py`
(esboço mínimo). Testes novos: `tests/test_init.py`, `tests/test_tmux.py`
(check/error). Zero novas dependências.
