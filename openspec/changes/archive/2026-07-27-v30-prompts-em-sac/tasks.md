# Tasks — v30-prompts-em-sac

## 1. Init gera em .sac/prompts/
- [x] 1.1 Testes: init cria `.sac/prompts/<nome>.md` e grava
      `prompt_file = ".sac/prompts/<nome>.md"`; check de existentes olha o
      novo caminho; banner/checklist atualizados
- [x] 1.2 Implementar em `sac/init.py`

## 2. Docs e textos
- [x] 2.1 README + beginner guides + help do init/uninstall

## 3. Fechamento
- [x] 3.1 Suíte verde + simulação de CI; `openspec validate` OK
- [x] 3.2 Validação ao vivo em dir descartável: init → contratos em
      `.sac/prompts/` → up injeta corretamente
