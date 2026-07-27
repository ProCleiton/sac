# Proposal — v32-lider-sem-poke-stale

## Por quê

O daemon itera TODOS os agentes no `_loop`, incluindo o líder. Com isso o
líder recebe re-cutucada de tarefa stale — mas o pane do líder é onde o
humano interage DIRETAMENTE com ele (`sac attach`). O poke de stale no líder
é ruído que interrompe a conversa humana, e pior: o texto manda o líder
reportar o bloqueio "ao líder" (auto-referência) e, após
`poke_escalate_after` pokes, o daemon "escala" o líder para ele mesmo
("worker <líder> sem progresso..."), gerando mais ruído na inbox dele. A
hierarquia de escalação é worker → líder → humano; acima do líder não há
agente para quem escalar — o humano já está no pane.

## O que muda

O líder deixa de receber re-cutucada de stale (daemon e `sac notify`
legado) e nunca é escalado para si mesmo. ENTREGAS ao líder continuam
inalteradas: replies de workers, escalações de workers e approval_prompts
seguem sendo injetados no pane dele — é o único canal worker → líder.

## Specs afetadas

- `core-mensageria` (MODIFIED: Stale detection (re-poke) com backoff;
  Daemon de entrega direta)
- `protocolo-escalacao` (MODIFIED: Daemon escala worker sem progresso ao
  líder)
