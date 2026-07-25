# Tasks — v18-sidebar-rodape-v2

## 1. Store: leituras para a sidebar v3
- [x] 1.1 Teste: `Store.inbox_count(agent)` retorna nº de arquivos `.msg` em `inbox/<agent>/` (0 se inexistente)
- [x] 1.2 Teste: `Store.last_event_age(agent)` retorna segundos desde o último evento do agente no `log.jsonl` (None sem eventos)
- [x] 1.3 Implementar 1.1 e 1.2 (suíte verde)

## 2. Sidebar v3 — árvore, modelo, badge, ocioso
- [x] 2.1 Teste: árvore com conectores `├─`/`└─` por window (2 agentes + agente único)
- [x] 2.2 Teste: modelo extraído de `--model` (`esteira/k3` → `kimi/k3`); sem model → só comando
- [x] 2.3 Teste: badge `(N)` com inbox pendente; ausente com inbox vazia
- [x] 2.4 Teste: `· 5m` desde último evento; ausente sem eventos
- [x] 2.5 Implementar em `_render_sidebar`/`commands.py` (suíte verde)

## 3. `sac status --mini`
- [x] 3.1 Teste: `3● 1!` com claimed/escalados; vazio com contadores zerados; vazio + exit 0 sem store
- [x] 3.2 Implementar flag `--mini` em `cli.py`/`cmd_status` (suíte verde)

## 4. Status bar v2
- [x] 4.1 Teste: `status-right` sem `MouseDrag`/`S-C-v`, com `#S:#W` e `#(sac status --mini`
- [x] 4.2 Implementar no `cmd_up` (suíte verde)

## 5. Fechamento
- [x] 5.1 Suíte completa verde + `openspec validate v18-sidebar-rodape-v2`
- [x] 5.2 Validação ao vivo: `sac up` em sessão de teste, conferir sidebar e rodapé renderizados
