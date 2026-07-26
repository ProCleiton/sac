# Tasks — v22-ux-iniciante-doctor

## 1. Hints no questionário do init
- [x] 1.1 Mapear todas as perguntas do questionário em `sac/init.py` e criar
      hints descritivos (sessão, socket, boot_wait, agent name, command,
      role, model, boot_wait individual, loops)
- [x] 1.2 Modificar `_ask()` (ou função equivalente) para exibir o hint antes
      de cada pergunta quando fornecido
- [x] 1.3 Escrever `InitHintTest` em `tests/test_init.py` com FakeInput — verificar
      que hints aparecem na saída capturada
- [x] 1.4 Validar ao vivo: `sac init` e inspecionar hints visualmente

## 2. Validação de harness no init
- [x] 2.1 Injetar `shutil.which()` na pergunta de `command` — se retornar None,
      exibir warning e permitir corrigir ou seguir
- [x] 2.2 Garantir que o warning não aborta o init (apenas informa)
- [x] 2.3 Escrever `InitHarnessValidationTest` em `tests/test_init.py` com
      FakeInput + monkeypatch de `shutil.which` — testar comando ausente
      (warning + seguir/corrigir) e comando presente (sem warning)
- [x] 2.4 Validar ao vivo: init com comando inexistente, init com comando
      existente

## 3. Checklist pós-init
- [x] 3.1 Implementar função `_print_onboarding()` em `sac/init.py` que imprime
      o checklist de 4 passos + dica de layout
- [x] 3.2 Chamar `_print_onboarding()` ao final do fluxo de sucesso do init
- [x] 3.3 Escrever `InitOnboardingTest` em `tests/test_init.py` com FakeInput —
      verificar que as 4 linhas do checklist e a dica aparecem na saída
- [x] 3.4 Validar ao vivo: `sac init` completo e conferir checklist no terminal

## 4. Comando `sac doctor`
- [x] 4.1 Implementar `cmd_doctor()` em `sac/commands.py` com a lógica de
      verificação por item (Python, tmux, socket, config, harnesses)
- [x] 4.2 Cada item essencial falho → exit 1; itens warning → exit 0
- [x] 4.3 Formatar saída como `[OK]`/`[FAIL]`/`[WARN]` com orientação
- [x] 4.4 Registrar subparser `doctor` em `sac/cli.py` com help
- [x] 4.5 Escrever `DoctorTest` em `tests/test_commands.py` com runners
      fakeáveis — testar: tudo OK, tmux ausente, Python < 3.11, harness
      ausente, sem config, tmux < 3.2, sem side-effects
- [x] 4.6 Validar ao vivo: `sac doctor` em ambiente real

## 5. README section "SAC and your harness"
- [x] 5.1 Redigir e inserir seção "SAC and your harness" (ou título en-US
      equivalente) em README.md, próximo ao bloco Concepts
- [x] 5.2 Conteúdo: plugins/skills sem extra config, tabela "o que vive onde",
      pre-warm manual, memória compartilhada via arquivos do workspace, mantra
      "stupid de propósito"
- [x] 5.3 Verificar que links e referências no README continuam íntegros

## 6. Fechamento
- [x] 6.1 Suíte de testes 100% verde
- [x] 6.2 `openspec validate v22-ux-iniciante-doctor` válido
