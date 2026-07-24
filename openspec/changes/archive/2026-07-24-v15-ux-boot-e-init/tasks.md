## 1. Progresso no up

- [x] 1.1 Escrever teste: `test_up_progress_lines` — FakeRunner, `cmd_up` com 2 agentes: verifica stdout contém `[1/2]`, `[2/2]`, "criando janela", "aguardando", "injetando prompt"
- [x] 1.2 Modificar `cmd_up`: loop de agents imprime `[N/total] nome: ação...` antes de cada etapa (new_session/new_window, split_window, sleep, inject_prompt)
- [x] 1.3 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_commands.py -q`

## 2. TmuxError + check()

- [x] 2.1 Escrever teste: `test_tmux_check_ok` — `tmux.check("has-session", "-t", "sac")` com rc=0 não levanta exceção
- [x] 2.2 Escrever teste: `test_tmux_check_fail` — `tmux.check("has-session", "-t", "sac")` com rc=1 levanta `TmuxError` com stderr
- [x] 2.3 Implementar `class TmuxError(Exception)` em sac/tmux.py; método `Tmux.check(*args)` que chama `_run()` e levanta TmuxError se rc≠0
- [x] 2.4 Escrever teste: `test_up_aborts_on_tmux_error` — `cmd_up` com FakeRunner rc=1 no new-session: aborta com TmuxError, não cria demais agentes
- [x] 2.5 Modificar `cmd_up`: usar `tmux.check()` para new_session, new_window, split_window; capturar TmuxError e re-levantar com mensagem aumentada
- [x] 2.6 Capturar `TmuxError` no `cli.py` main(): imprimir erro + sugestão (socket path), retornar 1
- [x] 2.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_tmux.py tests/test_commands.py -q`

## 3. mkdir -p do socket dir

- [x] 3.1 Escrever teste: `test_up_creates_socket_dir` — `cmd_up` com cfg.socket definido para path em tempdir: verifica que o diretório foi criado
- [x] 3.2 Escrever teste: `test_up_socket_dir_already_exists` — diretório já existe: não lança exceção
- [x] 3.3 Adicionar `Path(cfg.socket).parent.mkdir(parents=True, exist_ok=True)` no início de `cmd_up`, antes do has_session
- [x] 3.4 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_commands.py -q`

## 4. init — módulo e questionário

- [x] 4.1 Escrever teste: `test_init_creates_sac_toml` — `cmd_init(stdin=FakeInput(...))` gera sac.toml parseável e arquivo `prompts/leader.md`
- [x] 4.2 Escrever teste: `test_init_no_tty` — `cmd_init` com stdin não interativo (isatty=False): imprime erro e retorna 1
- [x] 4.3 Escrever teste: `test_init_existing_config_aborts` — com sac.toml existente e resposta "n" para sobrescrever: retorna 0 sem modificar
- [x] 4.4 Escrever teste: `test_validate_name_no_spaces` — input com espaço: função valida e repete pergunta
- [x] 4.5 Implementar `sac/init.py`:
  - `cmd_init(stdin=input, stdout=print, root=Path("."))` — função principal
  - `_ask(question: str, default: str, validate: Callable | None, stdin, stdout) -> str`
  - `_collect_config(stdin, stdout) -> Config` — faz as perguntas, monta Config
  - `_generate_toml(cfg: Config) -> str` — serializa Config para TOML
  - `_generate_prompts(cfg: Config, root: Path)` — escreve prompts/*.md
  - Templates embutidos: `LEADER_PROMPT`, `AUX_PROMPT`, `KIMI_NOTE`, `OPENCODE_NOTE`
- [x] 4.6 Registrar comando `init` no parser cli.py (sem argumentos)
- [x] 4.7 Verificar: `rtk test uv run --with-editable . python -m pytest tests/test_init.py -q`

## 5. init — templates de prompt

- [x] 5.1 Escrever teste: `test_prompt_template_leader` — template do leader contém "Papel: leader", "SAC_DONE", "sac done", "sac send user"
- [x] 5.2 Escrever teste: `test_prompt_template_aux` — template aux contém "Papel: aux", cabeçalho, reply sem done
- [x] 5.3 Implementar templates em `sac/init.py`: dicionário `PROMPT_TEMPLATES` com strings dos prompts (contrato SAC básico), mesclando papel + notas do harness

## 6. Validação final

- [x] 6.1 `rtk test uv run --with-editable . python -m pytest tests/ -q` — 182 passed
- [x] 6.2 `openspec validate v15-ux-boot-e-init`
- [x] 6.3 `git status --short` — apenas arquivos intencionais

## 7. Adicionais pós-proposta

- [x] A. `sac init` cria workspace COMPLETO: `.sac/` (inbox/, claimed/, done/) + socket dir pai + prompts/
- [x] B. Injeção consciente do tempo decorrido no `sac up`: `boot_start = time.monotonic()`, cada agente dorme `max(0, boot_wait - elapsed)`. Loading mostra espera restante.
