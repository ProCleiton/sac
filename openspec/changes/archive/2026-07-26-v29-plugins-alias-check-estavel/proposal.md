# Proposal — v29-plugins-alias-check-estavel

## Por quê

Dois achados do teste real no NFI (26/07):

1. `sac plugin status` (singular) falha com "invalid choice" — o usuário
   naturalmente digita no singular. O comando deve aceitar `plugin` como
   alias de `plugins`.
2. `sac plugins update --check` marcou `openspec v1.6.0-beta.1` como
   "atualização disponível" sobre a `v1.6.0` estável. Pré-releases (sufixo
   `-beta`, `-rc`, `-alpha`...) não são novidade para um pin estável — o
   check deve comparar só com a última tag ESTÁVEL do upstream.

## O que muda

- Subparser `plugins` ganha alias `plugin`.
- `_latest_tag` ignora tags de pré-release (com `-` no sufixo semver) ao
  determinar a última estável; tags estáveis novas continuam sinalizadas.

## Specs afetadas

- `plugins-canonicos` (MODIFIED: Comando sac plugins)
