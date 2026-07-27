# Proposal — v31-contrato-contexto-projeto

## Por quê

Observado em produção (NFI, 26/07): harnesses auto-carregam `AGENTS.md` e
seguem seus rituais de sessão DIRETA (ler `pendencias.md`, `regras-comuns.md`)
dentro da esteira — conflito com a memória e o workflow do SAC. A doutrina
"contratos não gerenciam AGENTS.md" cobre o contrato, mas não a auto-leitura
do harness. O conteúdo de projeto do AGENTS.md (convenções, stacks) é útil e
deve continuar sendo lido; os rituais de sessão direta, não.

## O que muda

Contratos canônicos (líder + aux) ganham uma linha na mensageria: arquivos
auto-carregados pelo harness (AGENTS.md, CLAUDE.md, regras-comuns.md) são
contexto de PROJETO; workflow e memória seguem o contrato SAC e o
`sac memory`; não ler pendencias.md nem executar rituais de sessão direta.

## Specs afetadas

- `cli` (MODIFIED: Catálogo de contratos canônicos)
