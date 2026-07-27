# memoria Specification

## Purpose
TBD - created by archiving change v26-memoria-longo-prazo. Update Purpose after archive.
## Requirements
### Requirement: Armazenamento SQLite da memória
O sistema SHALL manter memória de longo prazo em `<workspace>/.sac/memory.db`
(sqlite3 stdlib), criado lazy na primeira operação, com `journal_mode=WAL` e
`busy_timeout`. A tabela `memories` contém: `kind` (`tarefa`, `lição` ou
`referência`), `title`, `content`, `tags`, `importance` (1-5, default 3),
`status` (`ativa`/`arquivada`), `superseded_by`, `access_count`, `created_at`,
`last_accessed_at` e `agent`. Um índice FTS5 sobre title/content/tags é
mantido sincronizado por triggers; se FTS5 estiver indisponível, o sistema
degrada para busca `LIKE` com aviso. NENHUMA operação executa DELETE físico.

#### Scenario: criação lazy do banco
- **GIVEN** workspace sem `.sac/memory.db`
- **WHEN** a primeira operação de memória é executada
- **THEN** o banco é criado com schema completo (memories, fts, history)
- **AND** operações seguintes reutilizam o mesmo banco

#### Scenario: kind inválido é rejeitado
- **WHEN** `remember` recebe kind fora de tarefa/lição/referência
- **THEN** o sistema rejeita com mensagem clara e exit 1

#### Scenario: fallback sem FTS5
- **GIVEN** um ambiente sem FTS5
- **WHEN** `recall` recebe uma query
- **THEN** a busca usa `LIKE` e um aviso é emitido

### Requirement: Comando sac memory
O sistema SHALL expor `sac memory` com os subcomandos `remember`, `recall`,
`revise`, `forget`, `restore`, `decay`, `export` e `pack`. `recall` com query
usa FTS5 (ou LIKE no fallback); sem query retorna as mais recentes; memórias
retornadas têm `access_count` incrementado. `forget`/`restore` fazem
soft-delete (status arquivada/ativa). `revise` cria nova memória e marca a
anterior como `superseded_by`. `decay` arquiva deterministicamente: tarefas
mais velhas que N dias com importance ≤ 2 e access_count = 0; lições e
referências só com importance ≤ 1. `export` gera Markdown agrupado por kind.

#### Scenario: remember e recall por query
- **GIVEN** uma memória "API E2E roda na porta 9000" registrada
- **WHEN** `recall "porta 9000"` é executado
- **THEN** a memória é retornada com id, kind e importance
- **AND** seu access_count é incrementado

#### Scenario: recall não retorna arquivadas por padrão
- **GIVEN** uma memória com status arquivada
- **WHEN** `recall` é executado sem `--all`
- **THEN** a memória arquivada não aparece

#### Scenario: revise marca superseded
- **GIVEN** a memória #5 ativa
- **WHEN** `revise 5 -c "conteúdo atualizado"` é executado
- **THEN** uma nova memória é criada com o conteúdo
- **AND** a #5 fica com superseded_by apontando para a nova
- **AND** recall padrão retorna a nova, não a #5

#### Scenario: decay respeita elegibilidade
- **GIVEN** uma tarefa de 40 dias, importance 2, 0 acessos
- **AND** uma lição de 40 dias, importance 3, 0 acessos
- **WHEN** `decay --days 30` é executado
- **THEN** a tarefa é arquivada
- **AND** a lição permanece ativa

#### Scenario: decay dry-run não altera
- **WHEN** `decay --dry-run` é executado
- **THEN** as elegíveis são listadas e nenhuma é arquivada

### Requirement: Injeção orçada no contrato do leader
O sistema SHALL injetar o bloco de memória no contrato do líder
(`.sac/.sac/prompts/<leader>.md`) entre os marcadores `<!-- SAC-MEMORY:BEGIN -->` e
`<!-- SAC-MEMORY:END -->`, reescrevendo APENAS o conteúdo entre eles, de forma
idempotente, no `sac up` e após cada operação de escrita do `sac memory`. O
bloco contém instrução fixa de curadoria e as memórias ativas dentro de um
orçamento de caracteres (tarefas → lições → referências, importance desc,
truncamento sinalizado). Arquivo sem marcadores não é tocado; marcadores
corrompidos geram aviso e o arquivo não é modificado.

#### Scenario: rewrite idempotente entre marcadores
- **GIVEN** contrato do líder com marcadores e conteúdo manual fora deles
- **WHEN** a injeção roda duas vezes
- **THEN** o conteúdo fora dos marcadores é preservado byte a byte
- **AND** a seção entre marcadores reflete o estado atual do banco

#### Scenario: contrato sem marcadores não é tocado
- **GIVEN** `.sac/.sac/prompts/<leader>.md` sem os marcadores
- **WHEN** a injeção rodaria
- **THEN** o arquivo permanece inalterado

#### Scenario: orçamento de caracteres
- **GIVEN** memórias suficientes para exceder o orçamento
- **WHEN** `pack --budget N` é gerado
- **THEN** o bloco respeita N caracteres e sinaliza "… e N mais"

### Requirement: Curadoria auditada pelo leader
O contrato canônico de líder SHALL incluir instrução de curadoria da memória:
registrar com `remember`, consultar com `recall` antes de decidir, podar
tarefas concluídas com `forget`, lições superadas com `revise` e rodar `decay`
periodicamente. Toda operação que altera estado SHALL ser registrada na tabela
`history` (op, memory_id, detail, agent, timestamp), consultável via
`sac memory export --history`.

#### Scenario: template do líder contém instrução e marcadores
- **WHEN** o `sac init` gera o contrato do líder
- **THEN** `prompts/<leader>.md` contém os marcadores SAC-MEMORY
- **AND** contém a instrução de curadoria

#### Scenario: operações são auditadas
- **WHEN** remember, revise, forget, restore ou decay são executados
- **THEN** cada um grava uma entrada em `history` com op, memory_id e agent
  (de `SAC_AGENT`, quando presente)

