# Tasks — v26b-remove-loops

## 1. Schema e CLI
- [x] 1.1 Testes: config com `[[loops]]` → ConfigError orientando remoção;
      config sem loops carrega normal
- [x] 1.2 Remover `LoopConfig`, parsing e validação de loops de `sac/config.py`
- [x] 1.3 Remover `sac run` (subparser + dispatch + `cmd_run`) de
      `sac/cli.py` e `sac/commands.py`; ajustar testes que os cobrem

## 2. Wizard e doctor
- [x] 2.1 Remover a pergunta de loops do wizard (`sac/init.py`); ajustar os
      fluxos FakeInput dos testes (resposta de loops some)
- [x] 2.2 doctor: linha do config sem contagem de loops; ajustar testes

## 3. Contrato do líder
- [x] 3.1 Teste: contrato do líder contém disciplina de delegação e ciclo de
      revisão (delegar com `sac send`, cobrar revisão, iterar, escalar)
- [x] 3.2 Atualizar o contrato canônico em `sac/contracts.py`

## 4. Docs
- [x] 4.1 README + beginner guides (en/pt-BR): remover referências a loops e
      `sac run`; registrar a breaking change
- [x] 4.2 Após o archive: corrigir a linha "Purpose" das specs config/cli
      (mencionam loops)

## 5. Fechamento
- [x] 5.1 Suíte 100% verde
- [x] 5.2 `openspec validate v26b-remove-loops` válido
- [x] 5.3 Validação ao vivo em dir descartável: init sem pergunta de loops;
      config com `[[loops]]` falha com orientação
