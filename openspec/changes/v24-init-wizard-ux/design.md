# Design — v24-init-wizard-ux

## D1. Descoberta de config com fallback

Ordem de precedência para localizar o config:

1. `--config <path>` (flag explícita)
2. `$SAC_CONFIG`
3. `./.sac/sac.toml` (novo padrão)
4. `./sac.toml` (fallback legado)

Implementação: o `default` do argparse deixa de ser uma string fixa e vira
`None`; uma função `resolve_config_path(args_config)` aplica a ordem acima e
retorna o primeiro existente (para comandos que leem) ou o novo padrão
`.sac/sac.toml` (para `init`, que cria). `$SAC_CONFIG` continua tendo
prioridade sobre os caminhos de diretório — é como os panes da sessão viva
encontram o config (v19). `sac up` já exporta `SAC_CONFIG` com o caminho
resolvido; passa a exportar o caminho **efetivamente usado**.

Esteiras existentes (ex.: workspace Github, `sac.toml` na raiz) funcionam sem
nenhuma mudança via fallback. Não há migração automática.

## D2. Wizard — fluxo novo

```
SAC init — este wizard gera:
  .sac/sac.toml   (configuração da esteira)
  .sac/           (estado: inbox/claimed/done)
  prompts/*.md    (contrato de cada agente — edite à vontade depois)

1. Nome da sessão        hint: aparece em `sac attach` e `tmux ls` — ex.: esteira, nfi
2. Socket tmux           hint: ex.: ~/.sac-nfi/tmux.sock — isola a esteira do seu
                         tmux pessoal; Enter = sem socket (não recomendado)
3. Boot wait global      hint: segundos antes de injetar o prompt; harness lento
                         pede mais — ex.: 10 a 15
4. Número de agentes
5. Para cada agente:
   --- Agente 1 (leader — o orquestrador) ---
     hint: recebe suas mensagens e delega aos demais; é o pane do `sac attach`
   - Nome               hint: usado no `sac send` e `sac status` — ex.: leader, dev-1
   - Comando            default = 1º harness encontrado no PATH (kimi → opencode
                        → claude); hint "detectado no seu PATH"; sem detecção,
                        placeholder atual; validação com warning da v22 mantida
   - Contrato           SOMENTE agentes 2+: catálogo numerado (ver D3);
                        agente 1 recebe o contrato de leader sem pergunta
   - Modelo             hint: vazio = não passar --model
   - Boot wait específico  hint: só se ESTE harness demora mais que o global —
                         ex.: opencode pesado → 15; Enter = usa o global (10s)
   (pergunta "Papel (leader/aux)" REMOVIDA — agentes 2+ são aux)
6. Loops (s/N)           mantido como está
7. Agrupar em janelas? (s/N)  ver D4
8. Grava .sac/sac.toml + prompts/ + skeleton .sac/ + checklist pós-init
```

## D3. Catálogo de contratos canônicos

Superpowers e OpenSpec são a stack canônica do SAC. O catálogo é uma tabela
`nome → (descrição curta, template de contrato)` embutida em `sac/contracts.py`
(dados, não lógica):

| # | Papel | Essência do contrato |
|---|-------|---------------------|
| 1 | líder/orquestrador | recebe do usuário, decompõe, delega, consolida; escala bloqueios |
| 2 | desenvolvedor | TDD (teste antes do código), mudanças mínimas, debugging sistemático antes de propor fix |
| 3 | revisor de código | veredito por evidência (roda a suíte, lê o diff), bloqueantes vs. warnings |
| 4 | documentação | docs/espelhos fiéis ao código, OpenSpec atualizado |
| 5 | deploy/release | ciclo git por etapas com autorização, CI verde antes de merge |
| 6 | segurança | threat modeling do diff, segredos, superfícies de entrada |
| 7 | auxiliar genérico | contrato SAC básico (mensageria + SAC_DONE), sem disciplina extra |

Os templates **não exigem** o plugin superpowers nem o CLI openspec: as
disciplinas são descritas em texto puro. Se o harness tiver o plugin, o agente
reconhece as práticas pelos nomes das skills. Todos os contratos incluem o
protocolo de mensageria SAC (inbox/`sac next`/reply/`sac done`) — hoje gerado
pelos templates `LEADER_PROMPT`/`AUX_PROMPT`, que passam a ser o "corpo de
mensageria" comum ao qual a seção de disciplina do papel é anexada.

Edição posterior = abrir `prompts/<nome>.md`. O wizard não reedita contratos.

## D4. Agrupamento manual de `[windows]`

Pergunta única `Agrupar agentes em janelas? (s/N)` (default `N`). Se `s`,
loop de janelas:

- nome da janela (validado com `_valid_name`);
- agentes (nomes separados por espaço, validados contra os já criados;
  rejeita desconhecidos);
- disposição: `1` lado a lado (`;`) ou `2` empilhados (`,`);
- preview textual do resultado parcial antes de "adicionar outra janela? (s/N)".

Agentes fora de qualquer janela ficam com janela própria (comportamento atual
inalterado). A gramática `[windows]` não muda — o wizard apenas a escreve.

## D5. `sac uninstall`

1. Se a sessão tmux do config estiver no ar → recusa: "rode `sac down` antes".
2. Lista o que será removido: `.sac/` (config + estado), `prompts/`, e
   `sac.toml` da raiz se existir (legado).
3. Exige digitar o nome da sessão para confirmar; qualquer outra entrada
   aborta sem remover nada.
4. Não remove nada fora do diretório do workspace; não mata processos (a
   recusa do passo 1 garante).

## D6. Doctor e stack canônica

- `doctor` passa a reportar qual arquivo de config usou
  (`[OK] config loads (.sac/sac.toml, 8 agents, 1 loop)`).
- Se `./.sac/sac.toml` e `./sac.toml` existirem juntos → `[WARN]` de
  ambiguidade (o `.sac/sac.toml` vence).
- Novo item WARN (não essencial): CLI `openspec` no PATH — orientação de
  instalação se ausente. Detectar o plugin superpowers é harness-específico
  demais; vira nota no README, não item do doctor.

## Riscos operacionais do dogfooding

(mesmos cuidados da v23: esteira viva do workspace Github usa `sac.toml` na
raiz — o fallback a mantém intacta; desenvolvimento/testes usam tmp_path;
`pipx` editable serve o working tree, então `sac` global muda assim que o
código mudar — validar `sac init`/`doctor`/`uninstall` só em diretório
descartável até o merge.)
