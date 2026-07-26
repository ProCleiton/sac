# Proposal — v25b-init-modelos-e-catalogo-aux

## Por quê

Duas fricções do wizard observadas pelo usuário no uso real:

1. A pergunta de modelo é texto livre — o usuário tem que adivinhar os aliases
   válidos de cada harness. O init deve LISTAR os modelos disponíveis.
2. O catálogo de contratos dos agentes 2+ inclui "líder/orquestrador", mas só
   pode haver UM líder (o agente 1) — a opção é uma armadilha.

## O que muda

1. **Sugestão de modelos por harness** na pergunta "Modelo":
   - `kimi` → aliases das tabelas `[models."<alias>"]` de
     `~/.kimi-code/config.toml` (tomllib; só nomes de tabelas, nenhum segredo);
   - `opencode` → saída de `opencode models` (timeout curto);
   - outro harness / falha na detecção → cai na pergunta de texto livre atual.
   Com a lista, a resposta é o NÚMERO do modelo ou Enter (vazio = não passar
   `--model`, default do harness).
2. **Catálogo aux sem líder**: a lista numerada dos agentes 2+ exclui
   "líder/orquestrador" (6 opções, default: desenvolvedor). O agente 1 continua
   recebendo o contrato de líder sem pergunta.

## Non-goals

- Detectar modelos de harnesses desconhecidos (texto livre permanece).
- Cachear a lista do opencode (consulta ao vivo a cada init; timeout com
  fallback silencioso).

## Specs afetadas

- `cli` (ADDED: Sugestão de modelos por harness no init; MODIFIED: Catálogo de
  contratos canônicos)
