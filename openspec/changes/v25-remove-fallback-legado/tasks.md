# Tasks — v25-remove-fallback-legado

## 1. Descoberta sem fallback
- [x] 1.1 Ajustar testes de precedência em `tests/test_cli.py`: legado sozinho
      → None; comando com só `sac.toml` na raiz → exit 1 + mensagem de
      migração; oculto continua preferido
- [x] 1.2 Remover `CONFIG_LEGACY` da cadeia em `sac/cli.py`; mensagem de erro
      orienta migração quando `./sac.toml` existe
- [x] 1.3 `_default_config_path()` em `sac/commands.py` aponta só para o oculto
- [x] 1.4 Ajustar `test_uninstall_via_cli` (workspace só-legado: token cai
      para "sac"; uninstall ainda remove o legado)

## 2. Doctor
- [x] 2.1 Testes: WARN de legado ignorado quando ambos existem; mensagem de
      "sem config" menciona migração quando `./sac.toml` existe
- [x] 2.2 Implementar os ajustes em `cmd_doctor()`

## 3. Docs
- [x] 3.1 README: cadeia de descoberta sem fallback + nota de migração
- [x] 3.2 `docs/beginner-guide.md` (+ pt-BR): mesmo ajuste

## 4. Fechamento
- [x] 4.1 Suíte 100% verde
- [x] 4.2 `openspec validate v25-remove-fallback-legado` válido
