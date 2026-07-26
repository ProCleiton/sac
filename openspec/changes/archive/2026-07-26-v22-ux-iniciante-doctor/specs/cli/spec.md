## ADDED Requirements

### Requirement: Comando doctor — diagnóstico do ambiente

O sistema SHALL expor o comando `sac doctor` que verifica os pré-requisitos do
ambiente e reporta OK/FALHA por item com orientação de correção. O comando é
read-only (sem side-effects). Exit 0 se todos os itens essenciais estão OK;
exit 1 se algum item essencial falhar. Itens não essenciais (warning) não
alteram o exit code.

#### Checklist de verificação

| Item | Essencial | Critério |
|------|-----------|----------|
| Python version | sim | >= 3.11 |
| tmux presence | sim | `shutil.which("tmux")` não nulo |
| tmux version | sim | `tmux -V` retorna versão >= 3.2 (o layout grid exige) |
| Socket dir writable | sim | se `socket` configurado, diretório-pai existe e é gravável |
| Config loads | sim | `sac.toml` (ou `$SAC_CONFIG`) é parseável sem erro |
| Harnesses in PATH | não | cada `command` dos agentes em `[[agents]]` existe no PATH (warning individual) |

#### Formato de saída

```
[OK]  Python 3.12.5
[OK]  tmux 3.4
[OK]  socket dir ~/.sac-esteira is writable
[OK]  config loads (3 agents, 1 loop)
[WARN] harness 'kimi' not found in PATH (config may be for another machine)
[WARN] harness 'opencode' not found in PATH
```

Itens essenciais com FALHA usam `[FAIL]` e incluem orientação de correção:

```
[FAIL] tmux not found — install with: apt install tmux / brew install tmux
[FAIL] Python 3.10.2 < 3.11 — upgrade Python to 3.11+
```

#### Scenario: doctor — tudo OK

- **GIVEN** ambiente com Python >= 3.11, tmux >= 3.2, socket válido, config
  válida, todos os harnesses no PATH
- **WHEN** `sac doctor` é executado
- **THEN** todos os itens reportam `[OK]`
- **AND** exit code é 0

#### Scenario: doctor — tmux ausente (essencial)

- **GIVEN** `shutil.which("tmux")` retorna None
- **WHEN** `sac doctor` é executado
- **THEN** o item tmux reporta `[FAIL]` com orientação de instalação
- **AND** exit code é 1

#### Scenario: doctor — Python version insuficiente

- **GIVEN** `sys.version_info < (3, 11)`
- **WHEN** `sac doctor` é executado
- **THEN** o item Python reporta `[FAIL]` com upgrade instructions
- **AND** exit code é 1

#### Scenario: doctor — harness ausente (não essencial)

- **GIVEN** config com `command = "kimi"` e `shutil.which("kimi")` é None
- **WHEN** `sac doctor` é executado
- **THEN** o item do harness reporta `[WARN]` (não `[FAIL]`)
- **AND** exit code permanece 0 (outros itens essenciais OK)

#### Scenario: doctor — sem config (não essencial)

- **GIVEN** diretório sem `sac.toml` e sem `$SAC_CONFIG`
- **WHEN** `sac doctor` é executado
- **THEN** itens independentes de config (Python, tmux) rodam normalmente
- **AND** o item config reporta `[WARN]` (config não encontrada, ignorando
  checagens dependentes)
- **AND** items dependentes de config (socket, harnesses) são pulados/silenciados
- **AND** exit code é 0

#### Scenario: doctor — tmux version < 3.2

- **GIVEN** `tmux -V` retorna "tmux 3.1"
- **WHEN** `sac doctor` é executado
- **THEN** o item tmux version reporta `[FAIL]` com upgrade instructions
- **AND** exit code é 1

#### Scenario: doctor — sem side-effects

- **WHEN** `sac doctor` é executado
- **THEN** nenhum arquivo é criado, modificado ou removido
- **AND** nenhum processo tmux é iniciado ou terminado
- **AND** nenhum dado de mensageria é alterado
