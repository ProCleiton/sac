# Tasks — v26-memoria-longo-prazo

## 1. Módulo `sac/memory.py` — banco e CRUD
- [x] 1.1 Testes: criação lazy do banco em tmp_path; schema com FTS5; WAL/busy_timeout
- [x] 1.2 Testes: remember (kinds válidos/inválido, importance default 3,
      agent de SAC_AGENT); recall sem query (recentes) e com query (FTS5 rank);
      access_count incrementa; revise (superseded_by); forget/restore
      (soft-delete, recall não retorna arquivada sem --all)
- [x] 1.3 Implementar módulo (schema, triggers FTS, CRUD, history)
- [x] 1.4 Teste: fallback para LIKE quando FTS5 indisponível (mock)

## 2. decay, export, pack
- [x] 2.1 Testes: decay arquiva só o elegível (tarefa velha+i≤2+acessos 0;
      lição/referência exige i≤1; --dry-run não altera)
- [x] 2.2 Testes: export Markdown agrupado por kind; pack respeita orçamento
      (tarefas → lições → referências; trunca com "… e N mais")
- [x] 2.3 Implementar decay/export/pack

## 3. CLI `sac memory`
- [x] 3.1 Testes do wiring argparse (subcomandos, erros com exit 1)
- [x] 3.2 Registrar `memory` em `sac/cli.py` (usa o store_root da descoberta)

## 4. Injeção no contrato do leader
- [x] 4.1 Testes: rewrite da seção entre marcadores (idempotente, preserva o
      resto do arquivo); sem marcadores → não toca; marcadores corrompidos →
      aviso e não toca
- [x] 4.2 Implementar rewrite; chamar no `sac up` (antes da injeção) e após
      writes do `sac memory`
- [x] 4.3 Template canônico do líder em `sac/contracts.py` ganha os marcadores
      + instrução de curadoria fixa

## 5. Auditoria
- [x] 5.1 Testes: history registra ADD/REVISE/FORGET/RESTORE/DECAY com agent
- [x] 5.2 `sac memory export --history`

## 6. Docs e fechamento
- [x] 6.1 README + beginner guides (en/pt-BR): seção de memória
- [x] 6.2 Suíte 100% verde; `openspec validate v26-memoria-longo-prazo` OK
- [x] 6.3 Validação ao vivo em dir descartável: remember → recall → pack →
      up (contrato injetado) → forget → decay
