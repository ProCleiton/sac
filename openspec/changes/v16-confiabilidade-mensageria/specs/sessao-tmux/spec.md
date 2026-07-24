## MODIFIED Requirements

### Requirement: Envio de teclas com delay e Enter extra
O sistema SHALL, ao enviar teclas para panes tmux em contexto de mensageria
(daemon deliver, poke), usar delay de 0.2s entre o texto e o Enter, além de
incluir hint textual para destravar harness dormente.

#### Scenario: send-keys com delay para mensageria
- **WHEN** o daemon ou poke manual envia mensagem para um pane
- **THEN** o texto é injetado via `tmux send-keys -t <target> -l -- <text>` (literal)
- **AND** após 0.2s, um Enter é enviado via `tmux send-keys -t <target> Enter`
- **AND** o texto injetado contém hint `"SAC: mensagem — rode \`sac next\`"` ao final
