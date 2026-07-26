# Tasks — v21-ui-cores-wrap

## 1. Status bar v4 — paleta e segmentos powerline CCB
- [x] 1.1 Extrair paleta Catppuccin do `_DARK_STATUS` do CCB para constantes em `sac/commands.py`
- [x] 1.2 Reescrever `status-left`: modo (condicional DENTRO do atributo, sem vírgula) + U+E0B0 → `#[align=centre]` + workspace em cinza `#6c7086` + `#[align=left]`; SEM session_name nem mauve
- [x] 1.3 Reescrever `status-right`: worker red → U+E0B2 → `#(sac --version 2>/dev/null)` mauve → U+E0B2 → status-mini blue → U+E0B2 → data peach
- [x] 1.4 Configurar `status-style` bg=#1e1e2e fg=#cdd6f4, `status-left-length`=80, `status-right-length`=120
- [x] 1.5 Implementar flag `--version` em `sac/cli.py` (action="version", `importlib.metadata.version("sac")`)
- [x] 1.6 Alterar status-right para usar `#(sac --version 2>/dev/null)` em vez de string fixa
- [x] 1.7 Atualizar `AppearanceTest` — testar cores, separadores, workspace e tamanhos no format string

## 2. Caixas comms/tips com padding fixo 23
- [x] 2.1 Aumentar constante de padding em `_section()` para 23 (maximiza sem exceder SIDEBAR_MIN_COLS=28)
- [x] 2.2 Garantir que o box header não exceda `SIDEBAR_MIN_COLS` (28)
- [x] 2.3 Atualizar `SidebarV3Test` — verificar largura do box header
- [x] 2.4 Validar ao vivo: `sac sidebar` e inspecionar caixas

## 3. Truncamento na sidebar (NÃO wrap — wrap rejeitado pelo usuário)
- [x] 3.1 Manter `_truncate_ansi` como mecanismo de corte (wrap proposto e rejeitado na homologação)
- [x] 3.2 Garantir que linhas longas sejam truncadas com reset ANSI ao final
- [x] 3.3 Atualizar `SidebarV3Test` — testar truncamento em linha longa

## 4. Sidebar tree — sem modelo AI
- [x] 4.1 Implementar `_agent_model()` retornando basename do command (harness), NÃO o `--model`
- [x] 4.2 Remover exibição do modelo AI (--model) da linha do agente na árvore
- [x] 4.3 Atualizar testes — verificar que modelo AI não aparece

## 5. Sidebar label "sidebar" no pane-border-format
- [x] 5.1 Aplicar `pane-border-format=" #[fg=colour245] sidebar #[default] "` em `_mark_sidebar_pane`
- [x] 5.2 Atualizar spec delta em sessao-tmux (substitui "Sidebar sem borda de agente" da v20)

## 6. Tips — sem scrollbar, um atalho por linha
- [x] 6.1 Garantir que `TIPS_LINES` use um atalho por linha com indentação 2 espaços
- [x] 6.2 REMOVER qualquer implementação de barra de rolagem (scrollbar/trilho/polegar) — rejeitada visualmente pelo usuário

## 7. Largura da sidebar — SIDEBAR_PCT 18% com piso 28
- [x] 7.1 Alterar `SIDEBAR_PCT` de 15 para 18 em `sac/commands.py`
- [x] 7.2 Garantir que `client-resized` hook use o mesmo percentual
- [x] 7.3 Legado (dash) mantém largura fixa 30

## 8. Fechamento
- [x] 8.1 Suíte de testes 100% verde (293 passed)
- [x] 8.2 `openspec validate v21-ui-cores-wrap` válido
- [x] 8.3 Homologação ao vivo pelo usuário em múltiplas rodadas
