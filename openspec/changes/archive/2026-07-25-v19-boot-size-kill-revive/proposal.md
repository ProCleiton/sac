# Proposal: v19 — Tamanho explícito de sessão no boot + `sac kill` revive pane morto

## Contexto

Smoke test da esteira (25/07) expôs dois defeitos 100% reproduzíveis:

1. **Boot mata agentes opencode em layout grid**: a sessão tmux detached nasce 80x24. No layout `[windows]`, janelas com gramática `;` (lado a lado) geram panes de ~26 col. O opencode (bun) crasha com **SIGILL** ("Instrução ilegal (imagem do núcleo gravada)") ao receber o prompt injetado em pane estreito — reproduzido em sessão isolada: 3 panes de 26 col + paste do prompt → crash; mesmos 3 panes a 72 col (sessão 220x50) → sobrevive. Na esteira real, `docs` e `deployment` morrem em todo boot. O bug é do opencode/bun, mas o SAC não define tamanho da sessão no `new-session -d` — harnesses não deveriam bootar em 80x24.
2. **`sac kill` não revive agente com pane morto**: quando o pane do harness já morreu (caso acima), `sac kill <agente>` aborta com "pane do agente não encontrado" — não há caminho de recuperação além de `down`/`up` completo.

## Escopo

### Fix 1 — Tamanho explícito da sessão no `sac up` (spec `sessao-tmux`, `config`)
- Novas chaves opcionais `[session] width` / `height` (inteiros; default **220x50**).
- `Tmux.new_session()` aceita `width`/`height` e passa `-x/-y` ao `tmux new-session -d`.
- `cmd_up` usa os valores da config. Sem efeito em sessões já existentes (só vale na criação).

### Fix 2 — `sac kill` revive pane morto (spec `kill-agent`)
- Quando o pane do harness **não existe**, em vez de abortar: localiza a janela-alvo do agente (layout legado: janela com o nome do agente; layout grid: janela que contém o agente na gramática `[windows]`), acha o pane da sidebar nela (`@pane_role=sidebar`, fallback `pane_start_command`), e recria o harness via `split-window` full-width a partir da sidebar — com `@agent`, título, boot_wait, injeção de prompt e alerta de claimed, igual ao caminho normal.
- Se a janela/sidebar também não existir, aí sim retorna erro.
- O cenário antigo "pane não existe → erro" é substituído pelo revive.

### Fix 3 — Env de sessão nos panes (`SAC_ROOT` + `SAC_CONFIG`) (specs `cli`, `sessao-tmux`)
- Bug exposto no smoke: agente que roda `sac` com cwd fora da raiz da sessão resolve `./sac.toml` errado (no caso real: o repo `sac/` tinha um `sac.toml`+`.sac` de dogfooding — removidos a pedido do usuário — e o dev-1 caiu na sessão errada: "sessão inativa", "mensagem não está claimed"). A CLI já honra `SAC_ROOT` (v16), mas os panes nunca recebem essa env.
- `sac up` e `sac kill` exportam nos panes (harness, sidebar e dash): `SAC_ROOT=<raiz do store>` e `SAC_CONFIG=<caminho absoluto do sac.toml da sessão>`.
- CLI: o default de `--config` passa a ser `$SAC_CONFIG` quando definido (fallback `sac.toml`).
- Efeito colateral positivo: resolve a "limitação conhecida" do daemon/sidebar resolverem config pelo cwd.

### Fix 4 — Agnosticidade do produto (spec `config`)
- O SAC é produto público e gerenciador de harness **agnóstico**: código/templates gerados não podem referenciar ambiente específico. O `sac init` gerava prompts com alias/modelo locais hardcoded (`--model esteira/k3`, "DeepSeek V4 Flash", exemplo `opencode-go/deepseek-v4-flash` no questionário).
- `KIMI_NOTE`/`OPENCODE_NOTE` e o exemplo da pergunta de modelo ficam genéricos; o modelo é sempre escolha do usuário nos args do agente.
- Removidos do repo os restos de dogfooding (config de rodar o SAC contra si mesmo): `sac.toml`, `.sac/` e `prompts/{leader,dev,auditor}.md` — SAC gerencia workspaces, não a si mesmo.

## Fora de escopo
- Corrigir o SIGILL do opencode/bun (bug upstream; mitigação é o fix 1).
- Reconstrução pixel-perfect da geometria original do grid no revive (o pane revivido ocupa full-width ao lado da sidebar — funcional, não idêntico ao layout original; rebalanceamento de larguras pós-revive fica como backlog).

## Riscos
- Sessões criadas com 220x50 encolhem ao attach de cliente menor (comportamento normal do tmux com `aggressive-resize`); o que importa é o tamanho durante o boot.
- Revive em janela errada: mitigado resolvendo a janela pela gramática `[windows]` (fonte: config), não por heurística.
