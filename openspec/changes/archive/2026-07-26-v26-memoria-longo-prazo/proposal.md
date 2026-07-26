# Proposal — v26-memoria-longo-prazo

## Por quê

Agentes da esteira não têm memória além da sessão: tarefas, lições e
referências morrem com o contexto. O usuário decidiu (26/07) que o SAC terá
memória de longo prazo **própria**, em SQLite, cujo conteúdo é injetado no
contrato do leader — e que o leader é o **curador**, com instruções para podar
(tarefas concluídas, lições superadas, detalhes obsoletos) e não deixar crescer
indefinidamente.

Pesquisa comparativa (mem0, OpenMemory, memorymesh, OpenDream, memory-kernel,
basic-memory — relatório em 26/07) concluiu: nenhuma solução existente passa no
constraint stdlib-only do SAC e todas são retrieval-first (vetorial), quando o
SAC precisa de CRUD + curadoria — o líder já é o LLM que extrai e consolida.
Decisão aprovada: **módulo nativo `sac memory`**, roubando designs específicos:

- memory-kernel: schema (kind/importance/access_count/superseded_by),
  soft-delete, decay, pack com orçamento de caracteres
- memorymesh: vocabulário `remember/recall/forget`
- OpenDream: ciclo de curadoria add/modify/deprecate; injeção por marcadores
  idempotentes; lição de eval — memória escopada por workspace (poluição
  cross-projeto medida em −20pp)
- mem0: tabela de auditoria (`history`)
- basic-memory: export Markdown para inspeção humana

## O que muda

1. **Banco** `.sac/memory.db` — sqlite3 stdlib + FTS5. Tabela `memories`
   (kind: tarefa/lição/referência; title, content, tags, importance 1-5,
   status ativa/arquivada, superseded_by, access_count, timestamps) + tabela
   `history` (auditoria de toda operação) + índice FTS5.
2. **CLI** `sac memory` — `remember`, `recall` (FTS5 ou cronológico),
   `revise` (supersede), `forget`/`restore` (soft-delete; NUNCA DELETE
   físico), `decay` (poda determinística), `export` (Markdown), `pack`
   (bloco de injeção orçado).
3. **Injeção no contrato do leader** — seção entre marcadores
   `<!-- SAC-MEMORY:BEGIN/END -->` em `prompts/<leader>.md`, reescrita de
   forma idempotente pelo `sac up` e após writes, com orçamento de caracteres.
4. **Curadoria** — o contrato canônico de líder ganha seção de disciplina de
   memória (ciclo revisar → forget/revise/decay), com todas as operações
   auditadas na `history`.

## Non-goals

- Embeddings / busca vetorial / MCP server.
- Memória global compartilhada entre workspaces (decisão: só por workspace).
- Injeção nos contratos dos agentes aux (só leader; aux pode usar o CLI).
- DELETE físico de memórias (soft-delete sempre, alinhado ao preceito de
  soft delete do workspace).

## Specs afetadas

- `memoria` (nova spec — 4 requirements ADDED)

## Riscos

- FTS5 indisponível em alguma build de Python → o módulo detecta e degrada
  para `LIKE` (testado).
- Contrato do leader editado à mão na seção de memória → os marcadores
  delimitam; só o conteúdo entre eles é reescrito.
