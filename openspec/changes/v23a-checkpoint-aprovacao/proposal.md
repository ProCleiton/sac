## Why

O workflow do SAC hoje depende de disciplina de prompt para aprovações: o líder pergunta algo ao usuário via mensagem comum e "espera" que a resposta seja parseável. Não há garantia de runtime — a resposta é texto livre, o veredito exige triagem manual, e nada impede o líder de prosseguir sem resposta. A aprovação precisa virar uma primitiva do daemon com máquina de estado, para que "aguardar OK do usuário" seja um contrato e não uma convenção.

## What Changes

1. **Novo tipo de mensagem `approval_request`**: cabeçalho `type: approval_request` no .msg com campo `state: pending | approved | rejected`. Mensagens sem `type` (legado) continuam funcionando inalteradas.
2. **Comandos CLI `sac approve <id>` e `sac respond <id> <veredito> [motivo]`**: alteram o estado da approval_request e disparam reply automática ao líder com o veredito (e motivo, se houver).
3. **Flag `--approval` em `sac send`**: exclusiva do líder; cria a approval_request na inbox do `user`.
4. **Entrega pelo daemon no pane do líder**: o `user` não tem pane próprio — o usuário acompanha a sessão "cavalgando" o pane do líder via `sac attach`. O daemon renderiza a approval_request no pane do líder; o usuário responde de qualquer pane com `sac approve`/`sac respond`; o daemon grava o estado e entrega a reply automática ao líder.

## Non-goals

- Budgets de token/USD (não observável de forma harness-agnóstica).
- Sub-agentes in-process (manter arquitetura com harnesses externos).
- Trocar o transporte (manter mensageria em arquivos).
- Quebrar compatibilidade com os 8 prompts de papéis atuais (leader, dev-1, dev-2, docs, auditor, secops, revisor, deployment).
- Painel/UX dedicado de aprovações (o pane do líder é o ponto de contato do usuário).

## Specs afetadas

- `checkpoint-aprovacao` (nova): mensagem approval_request, máquina de estado, rota líder↔user via daemon.
- `cli` (delta): comandos `sac approve`, `sac respond`, flag `--approval` em `sac send`.
- `core-mensageria` (delta): aprovação como estado de mensagem; daemon renderiza approval_request no pane do líder.

## Nota

Parte 1/5 da `v23-orquestracao-primitivas` fatiada. Independente das demais partes; baseline da suíte: 486 passed.
