## Why

A experiência do usuário iniciante no SAC é funcional mas carece de orientação.
O `sac init` pergunta o que configurar sem explicar o porquê, não valida se o
harness existe no PATH (o usuário só descobre no primeiro `sac up`), e ao final
larga o usuário sem saber o que fazer a seguir. Também não existe um comando de
diagnóstico para depurar — o usuário precisa correr atrás de cada requisito
manualmente.

## What Changes

1. **Hints no questionário do init**: cada pergunta ganha uma linha curta de
   contexto ("por quê"), ex.: boot_wait → "tempo antes de injetar o prompt;
   harnesses lentos (kimi) precisam de mais".
2. **Validação de harness no init**: ao ler o `command` de cada agente, verificar
   `shutil.which()` e avisar se não existir no PATH (permitir corrigir ou seguir
   com warning).
3. **Checklist pós-init**: ao final do wizard, imprimir roteiro: (a) pre-warm do
   harness, (b) editar `prompts/*.md`, (c) `sac up`, (d) `sac attach`. Apontar o
   guia iniciante para layout `[windows]`.
4. **`sac doctor`**: novo comando read-only que verifica Python >= 3.11, tmux >=
    3.2, socket gravável, config válida, harnesses no PATH. Reporta OK/FALHA por
    item com orientação de correção. Exit 0 se essencial OK, 1 se falha essencial.
5. **Seção README "SAC and your harness"**: documenta a fronteira SAC ↔ harness
   — plugins/skills globais e de projeto funcionam sem configuração extra
   (o SAC não substitui nem desativa nada), tabela do que vive onde (harness
   config vs SAC config), pre-warm manual antes do primeiro `sac up`, disciplina
   de memória compartilhada via arquivos do workspace (não por plugins de
   memória de harness), e o mantra "SAC é stupid de propósito".

## Out of Scope

- Instaladores PyPI/SO/deb/rpm (futuro).
- Pre-warm automatizado de harness (passo manual do usuário; o doctor só lembra).

## Impact

- Código: `sac/init.py` (hints, validação, checklist), `sac/cli.py` (doctor),
  `sac/commands.py` (lógica do doctor), testes em `tests/test_init.py` e
  `tests/test_commands.py`.
- README.md: nova seção "SAC and your harness".
- Specs: `config` (wizard UX + README section), `cli` (doctor).
- Compatibilidade: sem quebra. Init continua funcional sem hints/validação
  (apenas mais verboso). Doctor é comando novo.
