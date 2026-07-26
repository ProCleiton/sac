## REMOVED Requirements

### Requirement: Resolução de config via env da sessão
**Reason**: Fallback legado removido (v25) — `./sac.toml` na raiz não é mais
considerado na descoberta. Substituído pelo requirement "Descoberta de config".
**Migration**: `mkdir -p .sac && mv sac.toml .sac/sac.toml` (o estado da
mensageria já vive em `.sac/`).

## ADDED Requirements

### Requirement: Descoberta de config
O sistema SHALL resolver o caminho do config pela ordem de precedência:
`--config` (flag explícita) > `$SAC_CONFIG` > `./.sac/sac.toml`. Nenhum outro
caminho é considerado — `./sac.toml` na raiz é ignorado. `sac up` SHALL
exportar `SAC_CONFIG` com o caminho efetivamente usado.

#### Scenario: SAC_CONFIG definido
- **WHEN** `sac <comando>` é executado sem `--config` e a env `SAC_CONFIG` está definida
- **THEN** a configuração é carregada do caminho em `SAC_CONFIG`, mesmo que o cwd não contenha config (ou contenha outro)

#### Scenario: Config oculto encontrado no diretório
- **WHEN** `./.sac/sac.toml` existe e não há `--config` nem `SAC_CONFIG`
- **THEN** a configuração é carregada de `./.sac/sac.toml`

#### Scenario: Legado na raiz é ignorado
- **WHEN** apenas `./sac.toml` existe (sem `.sac/sac.toml`) e não há `--config` nem `SAC_CONFIG`
- **THEN** o sistema NÃO carrega o legado
- **AND** imprime erro orientando a migração (`mkdir -p .sac && mv sac.toml .sac/`) ou `sac init`
- **AND** retorna exit 1

#### Scenario: --config explícito tem precedência
- **WHEN** `sac --config /caminho/x.toml <comando>` é executado com `SAC_CONFIG` definido
- **THEN** a configuração é carregada de `/caminho/x.toml`

#### Scenario: Nenhum config encontrado
- **WHEN** nenhum dos caminhos da cadeia existe
- **THEN** o sistema imprime erro indicando os caminhos tentados e sugere `sac init`
- **AND** retorna exit 1

## MODIFIED Requirements

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
| Config loads | sim | config resolvido pela cadeia de descoberta é parseável sem erro; saída indica qual arquivo foi usado |
| Harnesses in PATH | não | cada `command` dos agentes em `[[agents]]` existe no PATH (warning individual) |
| Legado ignorado | não | `./sac.toml` existe na raiz (warning: fallback removido — mover para `.sac/` ou apagar) |
| openspec CLI | não | `shutil.which("openspec")` não nulo (warning com orientação de instalação — stack canônica) |

#### Formato de saída

```
[OK]  Python 3.12.5
[OK]  tmux 3.4
[OK]  openspec found in PATH
[OK]  socket dir ~/.sac-esteira is writable
[OK]  config loads (.sac/sac.toml, 3 agents, 1 loop)
[WARN] harness 'kimi' not found in PATH (config may be for another machine)
[WARN] ./sac.toml existe na raiz mas é ignorado (fallback removido) — mova para .sac/ ou apague
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

- **GIVEN** diretório sem config em nenhum caminho da cadeia e sem `$SAC_CONFIG`
- **WHEN** `sac doctor` é executado
- **THEN** itens independentes de config (Python, tmux) rodam normalmente
- **AND** o item config reporta `[WARN]` (config não encontrada, ignorando
  checagens dependentes)
- **AND** se `./sac.toml` existir na raiz, o aviso inclui orientação de migração
- **AND** items dependentes de config (socket, harnesses) são pulados/silenciados
- **AND** exit code é 0

#### Scenario: doctor — config ambíguo (não essencial)

- **GIVEN** `./.sac/sac.toml` e `./sac.toml` existem no diretório
- **WHEN** `sac doctor` é executado
- **THEN** o item config indica qual arquivo foi usado (`.sac/sac.toml`)
- **AND** um `[WARN]` informa que o `./sac.toml` da raiz é ignorado (fallback
  removido) e orienta mover para `.sac/` ou apagar

#### Scenario: doctor — openspec ausente (não essencial)

- **GIVEN** `shutil.which("openspec")` retorna None
- **WHEN** `sac doctor` é executado
- **THEN** o item openspec reporta `[WARN]` com orientação de instalação
- **AND** exit code permanece 0

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
