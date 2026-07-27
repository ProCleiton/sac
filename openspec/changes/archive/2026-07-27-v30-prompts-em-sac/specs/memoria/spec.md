## MODIFIED Requirements

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
