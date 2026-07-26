## ADDED Requirements

### Requirement: Versionamento semver
O sistema SHALL adotar semver a partir de 1.0.0, com `pyproject.toml
[project] version` como fonte única da versão (lida por `sac --version` via
importlib.metadata). Minor para changes de feature, patch para fixes.

#### Scenario: versão vem do pacote
- **WHEN** `sac --version` é executado
- **THEN** a versão exibida é a do `pyproject.toml` do pacote instalado

### Requirement: Release por tag via GitHub Actions
O repositório SHALL ter um workflow de release disparado por push de tag
`v*`: a suíte de testes roda primeiro e, somente se verde, o workflow gera
sdist/wheel (`python -m build`) e publica o GitHub Release da tag com os
artifacts e notas geradas dos PRs.

#### Scenario: tag publica release
- **GIVEN** commit na main com o pyproject na versão X.Y.Z
- **WHEN** a tag `vX.Y.Z` é pushed
- **THEN** o workflow roda a suíte, gera os artifacts e publica o Release
  `vX.Y.Z` com eles anexados

#### Scenario: suíte vermelha bloqueia release
- **GIVEN** uma tag pushed com a suíte falhando
- **WHEN** o workflow roda
- **THEN** o Release NÃO é publicado e o workflow falha
