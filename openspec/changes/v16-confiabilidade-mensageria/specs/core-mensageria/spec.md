## MODIFIED Requirements

### Requirement: Armazenamento persistente de mensagens
O sistema SHALL armazenar mensagens como arquivos individuais no filesystem, com
raiz da fila determinada por `SAC_ROOT` (env/--sac-root/config) com fallback para
o diretório de trabalho corrente (`cwd / .sac`).

#### Scenario: Raiz explícita via SAC_ROOT
- **GIVEN** variável de ambiente `SAC_ROOT=/home/dev/Github` definida
- **WHEN** o Store é inicializado
- **THEN** `store.root` é `/home/dev/Github/.sac`
- **AND** todos os caminhos de inbox, claimed, done e log usam esta raiz

#### Scenario: Raiz explícita via --sac-root
- **GIVEN** `sac --sac-root /home/dev/Github` no comando
- **WHEN** o Store é inicializado
- **THEN** `store.root` é `/home/dev/Github/.sac`

#### Scenario: Raiz explícita via sac.toml
- **GIVEN** `[session]` contém `root = "/home/dev/Github"`
- **WHEN** o Store é inicializado
- **THEN** `store.root` é `/home/dev/Github/.sac`

#### Scenario: Fallback para cwd
- **GIVEN** nenhum SAC_ROOT, --sac-root ou config.root definido
- **WHEN** o Store é inicializado
- **THEN** `store.root` é `Path.cwd() / ".sac"` (comportamento atual)

#### Scenario: Hierarquia de precedência
- **WHEN** múltiplas fontes (env + cli + config) definem root
- **THEN** a precedência é: CLI `--sac-root` > env `SAC_ROOT` > config `[session].root` > cwd

### Requirement: Conclusão de mensagem (done com atomicidade)
O sistema SHALL concluir mensagens com escrita antecipada do log (write-ahead) e
verificação pós-move para garantir que o arquivo saiu de claimed.

#### Scenario: Done com write-ahead log
- **WHEN** `sac done <id>` é executado
- **THEN** o evento `done` é registrado em `log.jsonl` ANTES do move do arquivo
- **AND** o log é flushado via `fsync` antes do move

#### Scenario: Done move com verificação
- **WHEN** o arquivo é movido de claimed para done
- **THEN** o sistema verifica que `claimed/<id>.msg` NÃO existe mais
- **AND** se o arquivo original ainda existe (move falhou), loga `loop_error` com detalhes
- **AND** NÃO imprime "concluída ✅" — imprime mensagem de erro

#### Scenario: Done com sucesso
- **GIVEN** arquivo movido com sucesso de claimed para done
- **AND** verificação pós-move confirma que claimed está vazio
- **WHEN** a operação completa
- **THEN** imprime "concluída ✅" e o resumo informado
- **AND** o evento `done` está em `log.jsonl` (escrito antes do move)

### Requirement: Entrega de reply (deliver_reply robusto)
O sistema SHALL entregar replies com verificação de destino e fallback para poke
manual quando o daemon não está disponível.

#### Scenario: deliver_reply com destino válido
- **GIVEN** daemon ativo
- **WHEN** uma reply chega na inbox de um agente conhecido no `sac.toml`
- **THEN** o daemon entrega a reply no pane do destino
- **AND** registra evento `deliver` com agente, id e sender no log

#### Scenario: deliver_reply com destino inválido
- **GIVEN** daemon ativo
- **WHEN** uma reply chega na inbox de um destinatário que NÃO é agente conhecido
- **THEN** a reply permanece na inbox (não se perde)
- **AND** o daemon registra `loop_error` com identificação do problema

#### Scenario: Fallback de send sem daemon
- **GIVEN** daemon NÃO está ativo
- **WHEN** `sac send <agente> "<corpo>"` é executado
- **THEN** a mensagem é criada na inbox
- **AND** o sistema verifica se o agente tem pane ativo
- **AND** se sim, envia poke manual via tmux send-keys com Enter
- **AND** se não, exibe aviso no stderr

### Requirement: Daemon de entrega direta — poke com Enter forçado
O sistema SHALL, ao entregar mensagens via daemon, forçar um Enter extra com
delay e incluir hint textual para destravar agentes dormentes.

#### Scenario: Daemon entrega com Enter forçado
- **GIVEN** daemon ativo
- **WHEN** o daemon entrega uma mensagem nova no pane do agente
- **THEN** injeta o corpo via `tmux send-keys -t <pane> -l -- <body>`
- **AND** aguarda 0.2s
- **AND** envia `tmux send-keys -t <pane> Enter`
- **AND** ao final do corpo, adiciona `"SAC: mensagem — rode \`sac next\`"`
- **AND** registra evento `deliver` com agent, id e sender

#### Scenario: Poke extra no send sem daemon com Enter
- **GIVEN** daemon inativo e `sac send <agente>`
- **WHEN** o poke manual é enviado
- **THEN** o texto injetado inclui Enter com delay de 0.2s
- **AND** inclui hint textual: `"SAC: mensagem nova na inbox — rode \`sac next\`"`
