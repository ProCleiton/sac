# Tasks — v29-plugins-alias-check-estavel

## 1. Alias `plugin`
- [x] 1.1 Teste: `sac plugin status` funciona como `sac plugins status`
- [x] 1.2 Alias no subparser

## 2. Check só com tags estáveis
- [x] 2.1 Testes: `v1.6.0-beta.1` no topo NÃO é oferecida sobre pin estável;
      `v6.2.0` estável continua sinalizada
- [x] 2.2 Filtro de pré-release em `_latest_tag`

## 3. Fechamento
- [x] 3.1 Suíte verde + simulação de CI; `openspec validate` OK
