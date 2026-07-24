## Context

SAC v1.2 (branch `feat/daemon-coordenador`, PR #1) introduziu o daemon coordenador
com entrega direta de mensagens. A versão está em produção no repositório público
ProCleiton/sac. A v1.3 endereça fragilidades operacionais observadas no uso real:

- Loops `notify` e `log -f` sem proteção contra exceções (mortos silenciosos)
- Ausência de recuperação de harness travado (ciclo down+up = perda de estado)
- Sidebars de 30 cols achatadas após attach de clientes com terminais diferentes
- Inbox de agentes removidos do config acumulando lixo
- Untracked files do tooling local sem tratamento

Stack: Python 3.11+ stdlib apenas, tmux ≥ 3.0. Sem dependências externas.

## Goals / Non-Goals

**Goals:**
- Tornar `sac notify` e `sac log -f` resilientes a exceções (try/except + log)
- Implementar `sac kill <agente>` para reinicialização de harness no mesmo lugar
- Aplicar `set-hook client-resized` para persistir largura da sidebar (30 cols)
- Adicionar `sac status --clean` para remover mensagens órfãs
- Decidir e aplicar política de `.gitignore` para `.opencode/` e `AGENTS.md`

**Non-Goals:**
- Não substituir o daemon (v1.2) — o notify legado continua como fallback
- Não implementar detecção automática de harness travado (seria heurística frágil)
- Não modificar o layout de boot da sessão (já criado no up)
- Não mexer no contrato SAC_DONE / `sac done` — continua igual

## Decisions

### D1. Resiliência de notify — try/except genérico, não try/except por agente
- **Escolha**: envelopar `notify_sweep` inteiro em try/except, registrando
  `store.log("loop_error", error=str(exc))` — mesmo padrão do daemon.
- **Alternativa**: try/except dentro do loop de agentes em `notify_sweep`.
- **Motivo**: `notify_sweep` já varre agente por agente; exceção em um não deve
  abortar os demais. Mas por simplicidade e consistência com o daemon, o
  try/except fica no chamador (`cmd_notify`). Se um dia houver necessidade de
  granularidade, muda-se.

### D2. Mesmo padrão para cmd_log -f
- **Escolha**: try/except no loop `while True` do `cmd_log`, registrando erro.
- **Motivo**: a leitura de arquivo pode falhar (rotação, permissão); o loop deve
  continuar. Consistência com notify e daemon.

### D3. Kill — localizar pane do harness por SAC_AGENT no start_command
- **Escolha**: usar `tmux list-panes -s -t <session> -F "#{pane_id}|#{pane_start_command}"`
  filtrando por `SAC_AGENT=<nome>` (já implementado em `tmux.find_pane_id`).
- **Alternativa**: buscar por pane_title (que também é setado). O start_command
  é mais confiável pois é imutável após a criação do pane.
- **Motivo**: reusa lógica existente e testada.

### D4. Kill — recriação via split-window a partir da sidebar
- **Escolha**: localizar o pane da sidebar na janela do agente (via
  `pane_start_command` contendo "sac sidebar"), usar `split-window -t <sidebar_id> -h`
  para recriar o harness no mesmo lugar.
- **Alternativa 1**: `split-window -t <window> -h` sem referência à sidebar —
  arrisca criar um terceiro pane se a sidebar já foi morta.
- **Alternativa 2**: salvar o layout ID da janela e restaurar com `select-layout`.
  Mais complexo e frágil com hooks.
- **Motivo**: a sidebar é o ponto fixo da janela (nunca é morta pelo kill). Recriar
  a partir dela garante que o harness volte exatamente onde estava.

### D5. Hook client-resized — formato e escopo
- **Escolha**: `tmux set-hook -t <session> client-resized "run-shell 'for w in leader dev-1 auditor; do tmux resize-pane -t <session>:\$w -x 30; done'"`
  (lista fixa de agentes do config, montada em tempo de `sac up`).
- **Alternativa**: hook que varre todas as janelas com `list-panes` filtrando por
  "sac sidebar". Mais genérico, mas depende de parsing de saída no shell.
- **Motivo**: lista fixa é simples, determinística e não depende de parsing de
  tmux dentro do hook (que pode ser frágil). Atualizada no próximo `sac up`.
- **Risco**: se agente for adicionado ao config sem `sac up` (down+up), o hook
  não redimensiona a sidebar do novo agente. Aceitável: `sac up` é o único modo
  de criar janelas de agente.

### D6. Limpeza de órfãos — comando único, não automático
- **Escolha**: `sac status --clean` só executa sob demanda (flag explícita).
- **Alternativa**: limpeza automática no boot (`sac up`). Risco de remover
  mensagens que o usuário ainda quer consultar.
- **Motivo**: decisão conservadora — limpeza destrutiva requer ação explícita.

### D7. .opencode/ vai para .gitignore; AGENTS.md não existe — nada a fazer
- **Escolha**: adicionar `.opencode/` ao `.gitignore` existente.
- **AGENTS.md**: não existe no projeto. Se for gerado futuramente pelo kímica
  `/init` ou opencode, deve ser adicionado ao `.gitignore` também.
- **Motivo**: `.opencode/` contém node_modules (233MB+), skills e commands locais
  para tooling do desenvolvedor — não pertence ao repositório público.

## Risks / Trade-offs

- **[R1] Hook client-resized pode ter race condition com resize manual do usuário**:
  Se o usuário redimensionar a sidebar propositalmente, o hook pode reverter.
  **Mitigação**: o hook só dispara no evento client-resized (attach/reconnect),
  não em resize manual. O usuário pode redimensionar à vontade entre attaches.
- **[R2] Kill pode deixar processo filho órfão**:
  `tmux kill-pane` manda SIGTERM para o processo líder do pane. Se o harness
  tiver subprocessos (ex.: kimi rodando LLM), podem ficar órfãos.
  **Mitigação**: comportamento padrão do tmux — `kill-pane` encerra todo o
  grupo de processos do pane. Testar com harnesses reais.
- **[R3] Limpeza de órfãos é destrutiva**:
  Mensagens em inbox/claimed de agente removido são perdidas.
  **Mitigação**: flag explícita `--clean` + preservação de `done/` + log do evento.
- **[R4] Fallback notify legado sem resiliência**:
  Se o daemon estiver offline e o usuário usar `sac notify`, a resiliência
  só cobre o loop, não a entrega. Aceitável: daemon é o recomendado.

## Open Questions

- O hook `client-resized` deve ser registrado como `set-hook -g` (global) ou
  `-t <session>` (por sessão)? Sessão é mais seguro (não afeta outras sessões
  tmux do usuário). Decisão: por sessão.
- Em `sac kill`, após recriar o harness, deve aguardar `boot_wait` antes de
  re-injetar o prompt? Não — `sac inject` não aguarda; kill tampouco.
- A lista de sidebars no hook deve ser montada com nomes hardcoded ou via
  script runtime? Hardcoded (gerada no up) é mais simples e segura.

## Rollback Plan

Cada item é independente e reversível individualmente:

1. **Resiliência**: reverter try/except em cmd_notify/cmd_log. Sem migração.
2. **Kill**: remover comando do cli.py e função de commands.py. Mensagens claimed
   permanecem no filesystem.
3. **Hook**: `tmux set-hook -t <session> -u client-resized` desregistra.
4. **Limpeza**: sem rollback específico (operação destrutiva não é automática).
5. **.gitignore**: reverter a linha `.opencode/` no arquivo.
