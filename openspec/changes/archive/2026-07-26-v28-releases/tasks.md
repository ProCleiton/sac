# Tasks — v28-releases

## 1. Workflow de release
- [x] 1.1 Criar `.github/workflows/release.yml` (trigger tag `v*`; suíte →
      build → `gh release create` com artifacts + notes geradas)
- [x] 1.2 Validar YAML/sintaxe localmente (python yaml parse ou actionlint se
      disponível)

## 2. Versionamento e docs
- [ ] 2.1 Bump `pyproject.toml` 0.1.0 → 1.0.0 (commit de release na main)
- [x] 2.2 README: seção "Releases" (semver, processo tag→Actions, instalação
      da última versão)

## 3. Fechamento
- [x] 3.1 Suíte verde; `openspec validate v28-releases` OK
- [x] 3.2 Primeira release real: tag v1.0.0 pushed → workflow verde →
      Release publicado no GitHub
