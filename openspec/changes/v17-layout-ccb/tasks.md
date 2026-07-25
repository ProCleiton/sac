## 1. Parser da gramática de layout (`sac/layout.py`)

- [x] 1.1 Testes do parser (válidos: folha, `,` empilhado, `;` colunas, precedência `"a,b;c"`; inválidos: vazio, folha vazia, separador pendurado → ConfigError)
- [x] 1.2 Implementar `parse_spec()` (Node: Col | Row | Leaf)

## 2. Config `[windows]`

- [x] 2.1 Testes do `[windows]` (válido com ordem preservada; ausente → `{}`; agente desconhecido/duplicado/ausente → ConfigError)
- [x] 2.2 Implementar parsing + validações em `Config.load()`

## 3. Plano de layout com percentuais

- [x] 3.1 Testes do plano (50/50 empilhado; colunas desbalanceadas ~67/33; sidebar 15% com piso 28 col à esquerda)
- [x] 3.2 Implementar `build_plan(cfg) -> list[WindowPlan]` (percentuais sobre o espaço restante)

## 4. Materialização do grid no `cmd_up`

- [x] 4.1 Teste de materialização com FakeRunner (windows na ordem; splits com percentuais; sidebar 15%; `SAC_AGENT` + título por pane; select na entry window; dash por último)
- [x] 4.2 Teste de regressão: sem `[windows]`, sequência de chamadas idêntica à atual
- [x] 4.3 Implementar ramo `[windows]` no `cmd_up` consumindo `build_plan`

## 5. Sidebar v2 + toggle

- [x] 5.1 Teste de render (tree com `>`/`●`/`!`/`◐`/`·`/`*` + provider; comms com últimos 5 do log; tips presente)
- [x] 5.2 Teste do toggle (cria com `@pane_role=sidebar` + foco devolvido; mata quando presente; bind `prefix+e` no up)
- [x] 5.3 Implementar `cmd_sidebar` v2
- [x] 5.4 Implementar `sac sidebar --toggle`, marcação `@pane_role=sidebar` e bind no `cmd_up`

## 6. Bordas + status bar

- [x] 6.1 Teste de bordas/status (cor estável por hash; `pane-border-status top` por pane; status-left modo+branch; status-right agente+versão+data; window-status-format vazio)
- [x] 6.2 Implementar `agent_color()`, aplicação de bordas e status line no `cmd_up` (grid e legado) + hook `after-select-pane`

## 7. Hook de resize adaptado

- [x] 7.1 Teste do hook (grid: reaplica 15% por window; legado intacto)
- [x] 7.2 Implementar novo hook `client-resized` (ramo grid)

## 8. Integração e validação final

- [x] 8.1 Teste de integração (tmux real, `sac-itest`): grid sobe, panes nos lugares, sidebar renderiza v2
- [x] 8.2 `rtk test uv run --with-editable . python -m pytest tests/ -q` — suíte 100% verde
- [x] 8.3 `openspec validate v17-layout-ccb` + `rtk git status --short` (só arquivos intencionais)

## 9. Teste real ao vivo

- [x] 9.1 Adicionar `[windows]` ao `sac.toml` do repo, `sac down && sac up` — conferir grid, sidebar v2, bordas, status bar, toggle `prefix+e`
- [x] 9.2 Mensagem real leader→dev-1: indicadores (●/◐) e Comms atualizando na sidebar
- [x] 9.3 Capture das panes para o relatório; se falhar: abortar, corrigir, re-testar
- [x] 9.4 Registrar resultado no relatório de encerramento
