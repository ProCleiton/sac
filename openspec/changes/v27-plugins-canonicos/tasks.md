# Tasks — v27-plugins-canonicos

## 1. Manifest e comando `sac plugins`
- [x] 1.1 `sac/plugins_manifest.py` — dados dos 3 plugins (nome, tipo, repo,
      ref, extras por tipo)
- [x] 1.2 Testes com `SAC_HOME` em tmp + subprocess mockado: install clona na
      ref pinada; idempotente; sem rede → erro claro exit 1
- [x] 1.3 Testes: `update` faz fetch+checkout da ref; `--check` mostra pin ×
      upstream; `status` reporta instalado/ref/bin; `uninstall` remove com
      confirmação
- [x] 1.4 Implementar `cmd_plugins` em `sac/plugins.py` + subparser na CLI
- [x] 1.5 Materialização de bins: rtk (asset do release para ~/.sac/bin) e
      openspec (npm --prefix + shim) — mockados nos testes

## 2. Injeção nos agentes
- [x] 2.1 Testes: `_session_env` coloca `$SAC_HOME/bin` no início do PATH
- [x] 2.2 Testes: agente kimi ganha `--skills-dir $SAC_HOME/plugins/
      superpowers/skills` SÓ quando o plugin está instalado; agente opencode
      ganha `--pure`; agente não-kimi não ganha args extras
- [x] 2.3 Implementar no `cmd_up`/`_session_env`/`cmd_kill`
- [x] 2.4 Testes da tabela de adapters (`sac/harness_adapters.py`): kimi
      `--skills-dir` SÓ com superpowers instalado; opencode e mimo `--pure`;
      claude `--bare --plugin-dir`; copilot env `COPILOT_SKILLS_DIRS`; codex
      `-c skills.config=[...]`; harness desconhecido sem args/env extras
- [x] 2.5 Implementar `sac/harness_adapters.py` e migrar `_harness_cmd` para
      a tabela (kimi/opencode já feitos em 2.2/2.3 passam pelo adapter)

## 3. Contratos — seção Stack canônica
- [x] 3.1 Testes: contratos líder+aux contêm RTK obrigatório e ponteiro de
      skills do SAC; líder contém openspec + instrução de delegar com
      ferramenta canônica; documentação contém openspec
- [x] 3.2 Atualizar `sac/contracts.py` (paths com SAC_HOME resolvido em
      runtime na geração)

## 4. Doctor e init
- [x] 4.1 Testes: doctor WARN por plugin ausente/dessincronizado; OK quando
      tudo certo
- [x] 4.2 Implementar checks no `cmd_doctor`
- [x] 4.3 Init instala os plugins canônicos automaticamente (sem opção no
      wizard; falha → aviso sem abortar; checklist sem passo de plugins) (+ testes)

## 5. Docs e fechamento
- [x] 5.1 README + beginner guides (en/pt-BR): plugins canônicos
- [x] 5.2 Suíte 100% verde; `openspec validate v27-plugins-canonicos` OK
- [x] 5.3 Validação ao vivo: `SAC_HOME=/tmp/sac-home-test sac plugins install`
      real (rede) → status → doctor → up em dir descartável
