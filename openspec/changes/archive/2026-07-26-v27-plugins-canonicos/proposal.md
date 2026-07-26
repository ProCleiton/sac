# Proposal — v27-plugins-canonicos

## Por quê

Decisão do usuário (26/07): superpowers, openspec e RTK são **plugins
canônicos do SAC** — o SAC clona, instala e gerencia suas próprias cópias e
aponta os agentes para elas. Totalmente independente de instalações prévias
dos harnesses: dentro da esteira, o que vale é a cópia gerenciada pelo SAC.
Hoje cada um instala/atualiza por conta (o superpowers desta máquina veio do
plugin manager do kimi; o RTK de um script; o openspec do npm global) — sem
versão pinada, sem atualização coordenada, sem garantia de presença nos
agentes.

## O que muda

1. **Manifest canônico** (`sac/plugins_manifest.py` — dados): superpowers
   (skills, obra/superpowers), RTK (cli, rtk-ai/rtk), openspec (cli npm,
   Fission-AI/OpenSpec) — cada um com ref pinada.
2. **Layout SAC-owned**: clones em `~/.sac/plugins/<nome>/`; binários em
   `~/.sac/bin/` (rtk do release upstream; openspec via `npm install
   --prefix`).
3. **Comando `sac plugins`**: `install`, `update` (checkout da ref pinada;
   `--check` compara pin × upstream), `status`, `uninstall`.
4. **Injeção nos agentes** (`sac up`): `~/.sac/bin` no início do PATH de todo
   pane; `--skills-dir ~/.sac/plugins/superpowers/skills` nos args de agentes
   kimi (o flag substitui a auto-descoberta); contratos canônicos ganham a
   seção "Stack canônica SAC".
5. **Disciplina nos contratos**: RTK obrigatório em comandos verbosos
   (todos); superpowers — skill aplicável à tarefa (todos); openspec — líder
   e contrato de documentação; disciplina de delegação do líder passa a
   instruir a ferramenta canônica por tarefa.
6. **Doctor** verifica os 3 canônicos (instalado? ref certa? bin presente?)
   com WARN orientando `sac plugins install`; checklist pós-init ganha o
   passo.

## Non-goals

- Plugins além dos 3 canônicos; versões por workspace; escrever em configs
  de harness (`installed.json`, `~/.claude`, opencode.json); auto-update sem
  comando explícito; compilar RTK do source (usa o binário do release; se a
  plataforma não tiver release, WARN orientando instalação manual).

## Specs afetadas

- `plugins-canonicos` (nova spec — 5 requirements ADDED)
- `cli` (MODIFIED: Comando doctor, Comando init — checklist pós-init)

## Riscos

- Rede indisponível no install → erro claro, doctor aponta; testes mockam
  git/npm/curl — nenhum teste toca rede.
- Harness desconhecido (não-kimi) → skills via ponteiro no contrato
  (markdown puro), sem args extras.
