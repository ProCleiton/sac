## ADDED Requirements

### Requirement: Comando init — questionário interativo
O sistema SHALL expor o comando `sac init` que guia o usuário na criação de
`sac.toml` e `prompts/*.md` via input()/print().

#### Scenario: init interativo (TTY)
- **GIVEN** diretório sem `sac.toml`
- **AND** stdin é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema pergunta: nome da sessão (default "sac"), socket (Enter vazio = sem socket dedicado), leader (nome, harness, args, prompt_file)
- **AND** para cada worker: nome, harness (kimi/opencode/outro), args, role, boot_wait
- **AND** loops opcionais (nome, sequência de agentes, max_iterations)
- **AND** ao final, gera `sac.toml` no diretório corrente
- **AND** gera `prompts/*.md` com contrato SAC básico para cada agente

#### Scenario: init não interativo (sem TTY)
- **GIVEN** stdin não é TTY
- **WHEN** `sac init` é executado
- **THEN** o sistema imprime erro: "modo interativo requer terminal — use --config para apontar um sac.toml existente"
- **AND** retorna exit 1

#### Scenario: init com sac.toml existente
- **GIVEN** `sac.toml` já existe no diretório
- **WHEN** `sac init` é executado
- **THEN** o sistema pergunta se deseja sobrescrever (confirmação)
- **AND** se não, aborta com exit 0

#### Scenario: init valida nomes (charset)
- **GIVEN** usuário digita nome com espaço ou caractere especial
- **WHEN** `sac init` valida o nome
- **THEN** rejeita com "entrada inválida" e repete a pergunta
- **AND** só aceita `[A-Za-z0-9_-]`

#### Scenario: init valida round-trip do TOML gerado
- **GIVEN** todas as respostas coletadas
- **WHEN** o TOML é gerado internamente
- **THEN** o sistema valida o TOML com `tomllib.loads()` antes de escrever
- **AND** se inválido, aborta com erro "TOML gerado é inválido"

#### Scenario: init com prompts existentes
- **GIVEN** diretório `prompts/` já existe com arquivos .md
- **WHEN** `sac init` vai gerar prompts
- **THEN** pergunta se deseja sobrescrever
- **AND** se não, mantém prompts existentes

### Requirement: Progresso no up (TTY only)
O sistema SHALL exibir progresso por agente durante `sac up`, apenas quando
stdout é um terminal (TTY).

#### Scenario: up exibe progresso (TTY)
- **GIVEN** stdout é TTY
- **WHEN** `sac up` cria janelas e injeta prompts
- **THEN** para cada agente imprime `[N/total] nome: ação...`
- **AND** ações incluem "criando janela", "aguardando Xs", "injetando prompt"
- **AND** ao final imprime "sessão no ar com N agentes"

#### Scenario: up sem TTY — silencioso
- **GIVEN** stdout NÃO é TTY (redirecionado)
- **WHEN** `sac up` executa
- **THEN** nenhuma linha de progresso é impressa (apenas a mensagem final)

#### Scenario: up com fail-fast aborta no erro
- **GIVEN** socket com diretório-pai inexistente
- **WHEN** `sac up` tenta criar sessão
- **THEN** o comando ABORTA imediatamente com erro claro
- **AND** imprime sugestão de correção (ex.: "crie o diretório com mkdir -p")
- **AND** retorna exit 1
- **AND** nenhum agente é criado nem prompt injetado

### Requirement: Criação automática do diretório do socket
O sistema SHALL criar o diretório-pai do socket tmux se ele não existir.

#### Scenario: Socket dir criado no up
- **GIVEN** `cfg.socket = "~/.sac-esteira/tmux.sock"`
- **AND** `~/.sac-esteira/` não existe
- **WHEN** `sac up` inicia
- **THEN** o diretório `~/.sac-esteira/` é criado via `mkdir -p`
- **AND** a sessão tmux é criada com sucesso
