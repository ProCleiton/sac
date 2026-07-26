# Tasks — v20-statusbar-bordas-ccb

## 1. Status bar v3 — esquerda limpa, direita informativa
- [x] 1.1 Teste: `status-left` contém modo (KEY/COPY/INPUT) + `#{session_name}`, sem `#S:#W` nem lista de janelas
- [x] 1.2 Teste: `status-right` contém `#{@agent}`, `SAC`, `#(sac status --mini)` e `#(date +"%d/%m %a %H:%M")`; sem dicas estáticas
- [x] 1.3 Implementar format strings no `cmd_up` (suíte verde)

## 2. Pane-border-format com `@agent` em panes de harness
- [x] 2.1 Teste: `pane-border-format="#{@agent}"` em todo pane de harness (grid e legado)
- [x] 2.2 Teste: sidebar mantém `pane-border-format=""`
- [x] 2.3 Teste: cor da borda por hash do nome do agente (estável, 8 cores da palette)
- [x] 2.4 Teste: pane ativo realçado vs pane inativo
- [x] 2.5 Implementar no `cmd_up` (suíte verde)

## 3. Fechamento
- [x] 3.1 Suíte completa verde + `openspec validate v20-statusbar-bordas-ccb`
- [ ] 3.2 Validação ao vivo: `sac up` em sessão de teste, conferir status bar e moldura de panes
