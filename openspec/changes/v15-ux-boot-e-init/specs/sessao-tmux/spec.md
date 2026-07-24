## MODIFIED Requirements

### Requirement: Layout por janela com sidebar (progresso)
O sistema SHALL exibir progresso durante a criação da sessão tmux.

#### Scenario: Criação de janela com progresso
- **WHEN** `sac up` cria janelas e sidebars
- **THEN** imprime `[N/total] nome: criando janela...` antes de cada comando tmux

### Requirement: Janela dash (progresso)
A criação da dash SHALL exibir progresso.

#### Scenario: Criação da dash com progresso
- **WHEN** `sac up` cria a janela dash
- **THEN** imprime `[N/total] dash: criando janela...`

### Requirement: Fail-fast em comandos tmux críticos
O sistema SHALL abortar com erro claro se um comando tmux crítico falhar.

#### Scenario: Erro de socket aborta up
- **GIVEN** socket configurado com diretório inexistente (não criado automaticamente)
- **WHEN** `sac up` executa o primeiro comando tmux
- **THEN** a exceção `TmuxError` é levantada
- **AND** o cli.py captura e imprime mensagem com sugestão de correção
- **AND** o up retorna exit 1

#### Scenario: kill_pane falha — tolerante
- **GIVEN** pane inexistente
- **WHEN** `sac kill agent` chama `kill_pane`
- **THEN** o comando tmux falha silenciosamente (rc≠0 ignorado)
- **AND** o kill continua (tolerante)

#### Scenario: has_session falha — tolerante
- **WHEN** tmux não está instalado
- **THEN** `has_session()` retorna False (rc≠0 é falso, não exceção)
- **AND** não aborta o programa

### Requirement: Criação do diretório-pai do socket
O sistema SHALL criar o diretório do socket se não existir, antes do primeiro
comando tmux.

#### Scenario: mkdir antes do primeiro tmux
- **WHEN** `sac up` inicia
- **THEN** se `cfg.socket` está definido, `Path(socket).parent.mkdir(parents=True, exist_ok=True)` é executado
- **AND** a criação ocorre antes de `tmux new-session`
