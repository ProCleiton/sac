## MODIFIED Requirements

### Requirement: Comando sac plugins
O sistema SHALL expor `sac plugins` (alias: `sac plugin`) com subcomandos
`install`, `update`, `status` e `uninstall`. `install` clona cada plugin na
ref pinada e materializa binários (rtk: asset do release em `$SAC_HOME/bin/`;
openspec: `npm install --prefix` + shim), é idempotente e falha com erro
claro sem rede. `update` faz fetch+checkout da ref pinada; `--check` compara
a pin com a última tag ESTÁVEL do upstream (tags de pré-release — sufixo
`-beta`, `-rc`, `-alpha` etc. — são ignoradas), sem alterar nada. `status`
reporta por plugin: instalado, ref atual, bin presente. `uninstall` remove
clones e bins com confirmação.

#### Scenario: install clona na ref pinada e materializa bins
- **GIVEN** `$SAC_HOME` vazio
- **WHEN** `sac plugins install` é executado
- **THEN** cada repo é clonado e a ref pinada é checked out
- **AND** `$SAC_HOME/bin/rtk` e `$SAC_HOME/bin/openspec` existem

#### Scenario: install é idempotente
- **GIVEN** plugins já instalados na ref pinada
- **WHEN** `sac plugins install` é executado novamente
- **THEN** nada é reclonado e o resultado é sucesso

#### Scenario: update --check não altera nada
- **WHEN** `sac plugins update --check` é executado
- **THEN** pin × upstream estável são exibidos e nenhum arquivo muda

#### Scenario: pré-release ignorada no --check
- **GIVEN** pin `v1.6.0` e upstream com `v1.6.0-beta.1` como tag mais recente
- **WHEN** `sac plugins update --check` é executado
- **THEN** NÃO é sinalizada atualização para a pré-release

#### Scenario: alias plugin funciona
- **WHEN** `sac plugin status` é executado
- **THEN** o resultado é o mesmo de `sac plugins status`

#### Scenario: uninstall exige confirmação
- **WHEN** `sac plugins uninstall` é executado
- **THEN** os alvos são listados e só removidos após confirmação
