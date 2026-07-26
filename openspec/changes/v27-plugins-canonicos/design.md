# Design — v27-plugins-canonicos

## D1. Manifest e layout

`~/.sac/` é o território SAC-owned (home-level, não workspace — os plugins são
do sistema, compartilhados entre esteiras):

```
~/.sac/plugins/superpowers/   (clone git, ref pinada)
~/.sac/plugins/rtk/           (clone git, ref pinada)
~/.sac/plugins/openspec/      (clone git, ref pinada)
~/.sac/bin/rtk                (binário do release do RTK)
~/.sac/bin/openspec           (shim → node ~/.sac/plugins/openspec/bin/...)
```

Manifest (`sac/plugins_manifest.py`, dados puros):

```python
PLUGINS = [
  {"nome": "superpowers", "tipo": "skills", "repo": "https://github.com/obra/superpowers",
   "ref": "v6.1.1", "skills_dir": "skills"},
  {"nome": "rtk", "tipo": "cli-binary", "repo": "https://github.com/rtk-ai/rtk",
   "ref": "v0.43.0", "release_asset": "rtk-{os}-{arch}"},
  {"nome": "openspec", "tipo": "cli-npm", "repo": "https://github.com/Fission-AI/OpenSpec",
   "ref": "v1.6.0", "package": "@fission-ai/openspec"},
]
```

## D2. `sac plugins`

| Sub | Efeito |
|-----|--------|
| `install` | para cada plugin ausente/dessincronizado: clone (ou fetch+checkout da ref); materializa bin (`rtk`: download do asset do release para `~/.sac/bin/`; `openspec`: `npm install --prefix ~/.sac/plugins/openspec/.npm @fission-ai/openspec@<versão>` + shim em `~/.sac/bin/openspec`) |
| `update` | fetch + checkout da ref pinada em cada clone + re-materializa bins; `--check` só mostra pin × tag mais recente do upstream |
| `status` | por plugin: instalado?, ref atual, ref pinada, bin presente |
| `uninstall` | remove `~/.sac/plugins/` e `~/.sac/bin/` (com confirmação simples s/N) |

Sem rede → erro claro por plugin, exit 1. Idempotente: `install` em cima de
instalado só corrige o que falta. Raiz sobrescrevível por env `SAC_HOME`
(default `~/.sac`) — testes usam tmp.

## D3. Injeção nos agentes (`sac up`/`sac kill`)

1. Todo pane de agente recebe `PATH="$SAC_HOME/bin:$PATH"` (via `_session_env`).
2. **Adapters por harness** (`sac/harness_adapters.py` — tabela data-driven,
   consultada em `_harness_cmd`/`_session_env`):

| Harness | args extra | env extra |
|---|---|---|
| `kimi` | `--skills-dir $SAC_HOME/plugins/superpowers/skills` (só com superpowers instalado; substitui a auto-descoberta) | — |
| `opencode` | `--pure` | — |
| `mimo` | `--pure` (fork do opencode) | — |
| `claude` | `--bare --plugin-dir $SAC_HOME/plugins/superpowers` (superpowers É um plugin Claude com skills/ dentro; --bare pula auto-descoberta) | — |
| `copilot` | — | `COPILOT_SKILLS_DIRS=$SAC_HOME/plugins/superpowers/skills` |
| `codex` | `-c skills.config=[{path="$SAC_HOME/plugins/superpowers/skills",enabled=true}]` | — |
| outros/desconhecido | — (fallback: ponteiro no contrato) | — |

   Isolamento só onde há mecanismo limpo que não quebra autenticação
   (COPILOT_HOME/CODEX_HOME limpos quebrariam login — documentado; gemini,
   aider e goose não têm mecanismo confiável por invocação).
3. Contratos canônicos (`sac/contracts.py`) ganham seção "Stack canônica SAC"
   (texto com paths resolvidos em runtime — `~/.sac/...`):

   - **MESSAGING_AUX + MESSAGING_LEADER** (todos):
     - RTK obrigatório em comandos verbosos: `rtk err <build>`,
       `rtk test <suíte>`, `rtk git status|diff|log`, `rtk docker` — exceção:
       saída completa necessária (revisão linha a linha, valores exatos).
     - superpowers: skills canônicas em `~/.sac/plugins/superpowers/skills/` —
       leia a skill aplicável ao tipo de tarefa antes de começar.
   - **_LIDER disciplina** (além do acima):
     - openspec: specs e changes de projeto vivem em `openspec/` e são
       operados com o CLI `openspec` (validate, archive).
     - delegação: ao delegar, indique a ferramenta canônica da tarefa —
       RTK sempre; openspec quando envolver spec/change; skill superpowers
       aplicável.
   - **_DOCUMENTACAO disciplina**: ganha openspec (specs/changes atualizados
     e válidos).

## D4. Doctor e init

Doctor (WARN, não essenciais): por plugin — clone presente na ref pinada?
bin presente? (rtk/openspec). Saída:
`[OK]  plugin superpowers @ v6.1.1` / `[WARN] plugin rtk não instalado — rode 'sac plugins install'`.
Checklist pós-init ganha passo `sac plugins install` (antes do pre-warm).

## D5. Testes

Sem rede, sem git real: mocks de `subprocess.run` (git/curl/npm) e
`SAC_HOME` em tmp. Injeção: `_session_env` com PATH; args do kimi com
--skills-dir só quando plugin presente. Contratos: seção presente nos
gerados, paths do SAC_HOME. Doctor: 3 plugins ausentes/presentes.
