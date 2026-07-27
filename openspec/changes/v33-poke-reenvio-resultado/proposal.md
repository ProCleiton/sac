# Proposal — v33-poke-reenvio-resultado

## Por quê

Observado em operação: às vezes o worker conclui a tarefa e envia o
resultado ao líder, mas a entrega falha (daemon) e o líder nunca recebe. A
tarefa segue claimed, vira stale e o worker é re-cutucado — mas o poke atual
só diz "rode `sac done`" ou "reporte bloqueio". O worker então responde "já
enviei" e o trabalho TRAVA: o líder nunca recebe o resultado e o worker não
reenvia.

## O que muda

O texto do poke de stale do daemon passa a instruir o reenvio: se a tarefa
já foi concluída, o worker deve REENVIAR o resultado ao líder
(`sac send <líder> "..."`) mesmo que já tenha enviado antes — a entrega pode
ter falhado — e só então rodar `sac done <id>`. Reenvio duplicado é barato;
trabalho travado, não.

## Specs afetadas

- `protocolo-escalacao` (MODIFIED: Poke com instrução de reporte imediato)
