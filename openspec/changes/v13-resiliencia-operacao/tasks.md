## 1. Resiliência do notify

- [x] 1.1 Escrever teste que falha: `test_notify_sweep_exception_logged` — simula `store.stale()` lançando exceção e verifica que `store.log("loop_error")` é chamado com o erro, e o loop continua para o próximo agente
- [x] 1.2 Envelopar `notify_sweep` em try/except no `cmd_notify`: capturar `Exception` genérico, chamar `store.log("loop_error", error=str(exc))` e continuar o loop
- [x] 1.3 Verificar que suíte continua verde: `python3 -m unittest tests.test_notify -v`

## 2. Resiliência do log -f

- [x] 2.1 Escrever teste que falha: `test_log_follow_io_error` — simula `file.readline()` lançando IOError e verifica que `store.log("loop_error")` é chamado e o loop continua
- [x] 2.2 Envelopar `cmd_log` loop em try/except: capturar exceções de I/O, registrar `store.log("loop_error")`, continuar o loop com `time.sleep(1)` antes de tentar novamente
- [x] 2.3 Verificar suíte: `python3 -m unittest tests.test_commands -v`

## 3. Comando kill — infraestrutura tmux

- [x] 3.1 Escrever teste que falha: `TmuxTest.test_kill_pane` — `tmux.kill_pane("%2")` executa `tmux kill-pane -t %2`; `FakeRunner` verifica o comando chamado
- [x] 3.2 Implementar `Tmux.kill_pane(target: str)` em `sac/tmux.py` — delega para `self._run("kill-pane", "-t", self._ptarget(target))`
- [x] 3.3 Escrever teste que falha: `TmuxTest.test_kill_pane_unknown` — `kill_pane` com target inválido não lança exceção (tmux retorna rc≠0 mas não aborta)
- [x] 3.4 Escrever teste que falha: `TmuxTest.test_find_sidebar_pane` — `tmux.find_pane_by_command("sac sidebar")` retorna o pane_id do pane cujo `pane_start_command` contém "sac sidebar" na janela do agente
- [x] 3.5 Implementar `Tmux.find_pane_by_command(substring: str) -> str | None` em `sac/tmux.py` — busca em `list-panes -s -t <session> -F "#{pane_id}|#{pane_start_command}"`
- [x] 3.6 Verificar suíte: `python3 -m unittest tests.test_tmux -v`

## 4. Comando kill — lógica de negócio

- [x] 4.1 Escrever teste que falha: `test_cmd_kill_unknown_agent` — `cmd_kill(cfg, store, tmux, project_root, "fantasma")` levanta `ConfigError`
- [x] 4.2 Escrever teste que falha: `test_cmd_kill_no_session` — `cmd_kill` sem sessão ativa retorna erro com exit 1
- [x] 4.3 Escrever teste que falha: `test_cmd_kill_no_pane` — `cmd_kill` com sessão mas sem pane do harness retorna erro exit 1
- [x] 4.4 Escrever teste que falha: `test_cmd_kill_recreates_harness` — com `FakeRunner` que reporta pane do harness e sidebar: verifica `kill-pane` chamado, `split-window -h` chamado com env SAC_AGENT, `resize-pane -x 30` chamado, `select-pane -T <name>` chamado, prompt_file re-injetado, `store.log("kill")` chamado
- [x] 4.5 Escrever teste que falha: `test_cmd_kill_with_claimed` — agente com claimed pendente: verifica mensagem de re-alerta no novo pane
- [x] 4.6 Implementar `cmd_kill(cfg, store, tmux, project_root, agent_name) -> int` em `sac/commands.py` com o fluxo completo: validar agente → validar sessão → localizar harness → localizar sidebar → kill-pane → split-window com env → set_pane_title → resize sidebar → inject prompt → alertar claimed → log
- [x] 4.7 Registrar comando `kill` no `sac/cli.py`: parser com argumento posicional `agent`, case `"kill"` em main()
- [x] 4.8 Verificar suíte: `python3 -m unittest tests.test_commands -v`

## 5. Hook client-resized na sessão

- [x] 5.1 Escrever teste que falha: `test_up_registers_hook` — `cmd_up` com FakeRunner verifica que `set-hook -t <session> client-resized ...` foi chamado após criação da sessão
- [x] 5.2 Escrever teste que falha: `test_hook_valid_structure` — verificar que o comando do hook referencia `resize-pane -x 30` para cada janela de agente
- [x] 5.3 Implementar registro do hook em `cmd_up` (commands.py): após criar a sessão e antes do `execvp`/retorno, montar string com `tmux set-hook -t <session> client-resized "run-shell 'for w in <agent_names>; do tmux resize-pane -t <session>:\$w -x 30 2>/dev/null; done'"` e executar via `tmux._run`
- [x] 5.4 Verificar suíte: `python3 -m unittest tests.test_commands -v`

## 6. Limpeza de mensagens órfãs

- [x] 6.1 Escrever teste que falha: `StoreTest.test_clean_orphans_removes_inbox` — `store.clean_orphans(["leader", "dev-1"])` remove inbox/auditor/ e claimed/auditor/ e preserva done/auditor/
- [x] 6.2 Escrever teste que falha: `StoreTest.test_clean_orphans_logs_event` — verifica que o evento `clean` foi registrado em `log.jsonl` com `agents_removed`, `inbox_files`, `claimed_files`
- [x] 6.3 Escrever teste que falha: `StoreTest.test_clean_orphans_no_orphans` — sem órfãos, diretório não é criado/removido, retorna lista vazia
- [x] 6.4 Implementar `Store.clean_orphans(valid_agents: list[str]) -> dict` em `sac/store.py`: lista `inbox/` e `claimed/` no root, filtra os que não estão em `valid_agents`, conta arquivos, remove diretórios recursivamente, loga evento, retorna estatísticas
- [x] 6.5 Escrever teste que falha: `test_cmd_status_clean` — `cmd_status(cfg, store, tmux)` com flag `clean=True` executa `store.clean_orphans` e exibe resultado
- [x] 6.6 Implementar flag `--clean` no parser `status` em `sac/cli.py`, passar para `cmd_status`
- [x] 6.7 Modificar assinatura de `cmd_status` para aceitar `clean: bool = False`; se True, chama `store.clean_orphans` antes de exibir status
- [x] 6.8 Verificar suíte: `python3 -m unittest tests.test_commands tests.test_store -v`

## 7. Chore — .gitignore para untracked files do tooling local

- [x] 7.1 Verificar conteúdo de `AGENTS.md` (não existe hoje): confirmar que não há arquivo útil a commitar
- [x] 7.2 Verificar `.opencode/`: contém node_modules (~130MB), package-lock.json, skills e commands de tooling local — não deve ir para o repo
- [x] 7.3 Adicionar `.opencode/` ao `.gitignore` (após linha `# IDE`)
- [x] 7.4 Verificar `git status` antes e depois confirma que `sac/`, `tests/`, `docs/` não foram afetados

## 8. Validação final

- [x] 8.1 Rodar suíte completa: `python3 -m unittest discover -s tests -v` — 113 passed (baseline 97 + 16 novos)
- [x] 8.2 Verificar `openspec validate v13-resiliencia-operacao`
- [x] 8.3 Verificar `git status --short` para confirmar apenas arquivos intencionais alterados
