# Tasks — v24-init-wizard-ux

## 1. Descoberta de config com fallback
- [x] 1.1 Escrever testes de precedência em `tests/test_cli.py`: flag >
      `$SAC_CONFIG` > `./.sac/sac.toml` > `./sac.toml`; erro claro quando
      nenhum existe
- [x] 1.2 Implementar `resolve_config_path()` em `sac/cli.py` (default do
      argparse vira `None`) e aplicar nos comandos que leem config
- [x] 1.3 Garantir que `sac up` exporta `SAC_CONFIG` com o caminho efetivamente
      usado (teste)

## 2. Wizard — estrutura e hints
- [x] 2.1 Testes: abertura explicativa (o que será gerado e onde) aparece na
      saída
- [x] 2.2 Testes: hints com exemplos (sessão, socket, boot_wait global e
      específico) presentes na saída
- [x] 2.3 Testes: header `--- Agente 1 (leader` + hint do orquestrador;
      agentes 2+ NÃO recebem pergunta de papel e viram `aux`
- [x] 2.4 Implementar 2.1–2.3 em `sac/init.py`

## 3. Wizard — default inteligente de harness
- [x] 3.1 Testes com `shutil.which` mockado: kimi presente → default kimi;
      só opencode → default opencode; nenhum → placeholder atual; hint
      "detectado no seu PATH" só quando detectado
- [x] 3.2 Implementar detecção (ordem kimi → opencode → claude) mantendo a
      validação com warning da v22

## 4. Catálogo de contratos canônicos
- [x] 4.1 Criar `sac/contracts.py` com a tabela de 7 papéis (D3) — dados puros
- [x] 4.2 Testes: agente 1 recebe contrato de leader sem pergunta; agentes 2+
      veem o catálogo numerado (default desenvolvedor); escolha inválida
      repete a pergunta
- [x] 4.3 Testes: `prompts/<nome>.md` gerado contém protocolo de mensageria
      SAC + disciplina do papel escolhido; contratos não exigem
      plugin/CLI externo
- [x] 4.4 Implementar: catálogo no wizard + geração unificada
      (corpo de mensageria + seção de disciplina)

## 5. Wizard — agrupamento de janelas
- [x] 5.1 Testes: resposta `N` → nenhuma `[windows]` no config
- [x] 5.2 Testes: janela com agentes válidos → `[windows]` correto
      (`;` lado a lado, `,` empilhados); agente desconhecido rejeitado;
      preview exibido; agentes fora de janelas mantêm janela própria
- [x] 5.3 Implementar o loop de janelas no wizard

## 6. Init escreve em `.sac/`
- [x] 6.1 Testes: init gera `.sac/sac.toml` (não `sac.toml` na raiz),
      skeleton `.sac/` e `prompts/` na raiz; round-trip TOML válido
- [x] 6.2 Implementar a mudança de caminho + checklist pós-init atualizado

## 7. `sac uninstall`
- [x] 7.1 Testes: sessão no ar → recusa com orientação; confirmação errada →
      aborta sem remover; confirmação correta → remove `.sac/`, `prompts/` e
      `sac.toml` legado; nada fora do workspace é tocado
- [x] 7.2 Implementar `cmd_uninstall()` em `sac/commands.py` + subparser em
      `sac/cli.py`

## 8. Doctor e stack canônica
- [x] 8.1 Testes: doctor reporta qual arquivo de config usou; WARN quando os
      dois caminhos existem; WARN para `openspec` ausente do PATH
- [x] 8.2 Implementar os três itens em `cmd_doctor()`

## 9. Docs
- [x] 9.1 README: seção "Stack canônica" (superpowers + OpenSpec — o que o
      SAC espera/usa, o que é opcional) + atualizar caminho do config
- [x] 9.2 `docs/beginner-guide.md` (+ pt-BR): novo fluxo do wizard, catálogo
      de contratos, `sac uninstall`, config em `.sac/`

## 10. Fechamento
- [x] 10.1 Suíte 100% verde
- [x] 10.2 `openspec validate v24-init-wizard-ux` válido
- [x] 10.3 Validação ao vivo em diretório descartável: init completo →
      doctor → up → down → uninstall
