# Design — v26-memoria-longo-prazo

## D1. Módulo e banco

Novo módulo `sac/memory.py` (stdlib apenas: `sqlite3`, `json`, `datetime`).
Banco em `<workspace>/.sac/memory.db` (Store root — segue `SAC_ROOT`/root do
config). Criação lazy na primeira operação. `PRAGMA journal_mode=WAL` e
`busy_timeout=5000` (agentes podem escrever em paralelo).

Schema:

```sql
CREATE TABLE memories (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('tarefa','lição','referência')),
  title TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '',           -- espaço-separado, simples
  importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
  status TEXT NOT NULL DEFAULT 'ativa' CHECK (status IN ('ativa','arquivada')),
  superseded_by INTEGER REFERENCES memories(id),
  access_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,                -- ISO 8601
  last_accessed_at TEXT NOT NULL,
  agent TEXT NOT NULL DEFAULT ''           -- quem registrou (SAC_AGENT)
);
CREATE VIRTUAL TABLE memories_fts USING fts5(title, content, tags,
                                             content='memories', content_rowid='id');
CREATE TABLE history (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, agent TEXT NOT NULL DEFAULT '',
  op TEXT NOT NULL, memory_id INTEGER, detail TEXT NOT NULL DEFAULT ''
);
```

Triggers mantêm o FTS sincronizado (insert/update/delete).

## D2. CLI `sac memory`

Saída sempre uma linha por memória: `#<id> [<kind>] (i<importance>) <title>`.
Subcomandos:

| Sub | Assinatura | Efeito |
|-----|-----------|--------|
| `remember` | `<kind> "<title>" [-c content] [-t tags] [-i N]` | insert + history(ADD); imprime o id |
| `recall` | `["query"] [--kind K] [--limit N=10] [--all]` | com query: FTS5 rank; sem: recentes; incrementa access_count e last_accessed_at dos retornados; `--all` inclui arquivadas |
| `revise` | `<id> [-t title] [-c content] [-i N]` | insert da revisão + antiga vira `superseded_by=<novo>` + history(REVISE) |
| `forget` | `<id>` | status→arquivada + history(FORGET) |
| `restore` | `<id>` | status→ativa + history(RESTORE) |
| `decay` | `[--days N=30] [--dry-run]` | arquiva tarefas com `last_accessed_at` mais velha que N dias, importance ≤2 e access_count=0; lições/referências exigem importance ≤1; imprime o que arquivou |
| `export` | `[> file.md]` | Markdown agrupado por kind (ativas; `--all` inclui arquivadas) |
| `pack` | `[--budget N=4000]` | bloco de injeção (ver D3) dentro do orçamento de caracteres |

Sem subcomando → help. Erros (id inexistente, kind inválido) → mensagem clara,
exit 1. NENHUM subcomando executa DELETE físico.

## D3. Injeção no contrato do leader

`pack` monta:

```
<!-- SAC-MEMORY:BEGIN -->
## Memória de longo prazo (`.sac/memory.db`)

Você é o curador desta memória. Regras:
1. Registre: `sac memory remember tarefa|lição|referência "<título>" -c "<conteúdo>"`.
2. Consulte: `sac memory recall "<query>"` antes de decidir — não redescubra.
3. Pode regularmente: tarefa concluída → `sac memory forget <id>`; lição superada →
   `sac memory revise <id>`; rode `sac memory decay` periodicamente.
4. Nunca delete fisicamente; tudo é auditado.

### Tarefas em aberto
#12 [tarefa] (i4) Migrar esteira para config oculto — ...
### Lições
#7 [lição] (i5) Archive OpenSpec exige nomes originais de scenarios — ...
### Referências
#3 [referência] (i3) API E2E roda na porta 9000 — ...
<!-- SAC-MEMORY:END -->
```

Orçamento (default 4000 chars): entram primeiro tarefas ativas (importance
desc, recentes), depois lições, depois referências; trunca com linha
`… e N mais (sac memory recall)`. A instrução de curadoria é parte fixa do
bloco (fora do orçamento? não — dentro, mas garantida: o orçamento mínimo
cobre instrução + aviso de truncamento).

**Quem reescreve**: `sac up` (antes de injetar o prompt) e cada `sac memory`
que altera o banco (remember/revise/forget/restore/decay) reescrevem a seção
entre marcadores no `prompts/<leader>.md` — apenas se o arquivo existir e
contiver os marcadores. O template canônico do líder (`sac/contracts.py`)
passa a incluir os marcadores vazios. Injeção idempotente: sem marcadores →
o arquivo não é tocado (contratos antigos/customizados seguem funcionando).

## D4. Curadoria auditada

Toda operação que muda estado grava em `history` (op, memory_id, detail,
agent de `SAC_AGENT` quando presente). `sac memory export --history`
mostra o rastro. Isso permite ao usuário auditar a poda do líder.

## Riscos operacionais

- FTS5 ausente → fallback para `LIKE '%q%'` com aviso no stderr (testado).
- Concorrência de writes (2 agentes) → WAL + busy_timeout; operações são
  curtas e atômicas por statement.
- Contrato do leader com marcadores corrompidos (BEGIN sem END) → rewrite
  falha com aviso e NÃO toca o arquivo.
