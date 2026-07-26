# Proposal — v28-releases

## Por quê

O SAC está na 27ª change mas reporta `0.1.0`: não há tags, nem GitHub
Releases, nem CI. Decisão do usuário (26/07): o repositório deve ter releases
de verdade, refletindo a versão atual.

## O que muda

1. **Semver** a partir de **1.0.0**; `pyproject.toml` é a fonte da versão
   (`sac --version` já lê de importlib.metadata). Minor por change de
   feature, patch por fix.
2. **`.github/workflows/release.yml`** — push de tag `v*` dispara: suíte
   completa → `python -m build` → `gh release create <tag> dist/*
   --generate-notes`. Sem suíte verde, sem release.
3. **Processo de release** (documentado no README): commit
   `chore(release): vX.Y.Z` bumpando o pyproject → tag → push da tag →
   Actions publica.
4. **Primeira release: v1.0.0** na main atual.

## Non-goals

- Publicar no PyPI (futuro, já registrado no backlog de instaladores).
- CI de PRs, release-please, assinatura de artifacts.

## Specs afetadas

- `releases` (nova spec — 2 requirements ADDED)
