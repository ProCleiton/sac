# Proposal — v26b-remove-loops

## Por quê

Decisão do usuário (26/07): os loops declarados `[[loops]]` são contra a
filosofia do SAC ("coordenador estúpido, inteligência nos contratos") — é o
daemon roteando tarefa por conta própria. São rígidos (sequência e
max_iterations fixas), sobrepõem conceitualmente as primitivas de orquestração
da v23, e adicionam uma pergunta ao wizard. A delegação e os ciclos de revisão
passam a ser **disciplina do contrato do líder** (com as práticas do
superpowers). Usuário optou pela **remoção direta**, sem período de deprecação.

## O que muda

1. **`sac run` removido** da CLI (era o gatilho dos loops).
2. **`[[loops]]` removido do schema**: config contendo `[[loops]]` →
   `ConfigError` claro orientando a remoção da seção (a delegação é via
   contrato do líder).
3. **Wizard sem pergunta de loops** (menos uma pergunta — direção "usuário
   preguiçoso").
4. **doctor** sem contagem de loops na linha do config.
5. **Contrato canônico do líder** ganha disciplina de delegação e ciclo de
   revisão: decompor e delegar com `sac send`, cobrar revisão do trabalho dos
   auxiliares, iterar até convergir, escalar ao usuário só em bloqueio real.
6. **Docs** (README + guias) sem referências a loops.

## Breaking change

Configs com `[[loops]]` param de carregar com erro claro (a esteira do
workspace Github tem o loop `dev-review` — o usuário já vai recriá-la com o
wizard novo, que não pergunta mais loops).

## Non-goals

- Período de deprecação com WARN (decisão explícita do usuário: remoção direta).
- Substituir a execução de loops por outro mecanismo no daemon (a orquestração
  fina é da v23; a disciplina é do contrato do líder).

## Specs afetadas

- `config` (REMOVED: Declaração de loops; MODIFIED: Geração de sac.toml via
  template, purpose)
- `cli` (REMOVED: Execução de loops declarados; MODIFIED: Comando init,
  Comando doctor, Sidebar informativa)
